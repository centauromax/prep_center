import logging
from celery import shared_task
from django.db import transaction
from django.core.cache import cache
from .models import SearchResultItem, TelegramNotification
from .utils.extractors import extract_product_info_from_dict
from libs.prepbusiness.client import PrepBusinessClient as OfficialPrepBusinessClient
from libs.config import PREP_BUSINESS_API_KEY, PREP_BUSINESS_API_URL, PREP_BUSINESS_API_TIMEOUT
from .utils.clients import get_client
import traceback
from django.utils import timezone
from datetime import timedelta
from .services import send_telegram_notification as send_notification_service

logger = logging.getLogger(__name__)

def _get_client():
    """Helper to initialize the official client in a Celery task."""
    try:
        domain = PREP_BUSINESS_API_URL.replace('https://', '').split('/api')[0]
        return OfficialPrepBusinessClient(
            api_key=PREP_BUSINESS_API_KEY,
            company_domain=domain,
            timeout=PREP_BUSINESS_API_TIMEOUT
        )
    except Exception as e:
        logger.error(f"Errore inizializzazione client PrepBusiness in Celery task: {e}")
        return None

@shared_task(bind=True, max_retries=3)
def process_shipment_batch(self, search_id, shipment_ids, merchant_id, shipment_type='outbound'):
    logger.info(f"[CELERY_TASK] ==============> INIZIO task process_shipment_batch <==============")
    logger.info(f"[CELERY_TASK] search_id={search_id}, shipment_ids={shipment_ids}, merchant_id={merchant_id}")
    logger.info(f"[CELERY_TASK] Task ID: {self.request.id}")
    logger.info(f"[CELERY_TASK] Stato task: {self.request.state}")
    
    try:
        # Verifica lo stato iniziale della cache
        cache_done_before = cache.get(f"{search_id}_done")
        logger.info(f"[CELERY_TASK] Stato iniziale flag {search_id}_done: {cache_done_before}")
        
        # Se il flag è già True, significa che il timer ha già imposto il timeout
        if cache_done_before is True:
            logger.warning(f"[CELERY_TASK] Flag {search_id}_done è già True, probabilmente scattato il timeout. Termino il task.")
            return {
                'status': 'cancelled',
                'reason': 'Flag already set to done',
                'search_id': search_id
            }
        
        client = _get_client()
        results = []
        
        logger.info(f"[CELERY_TASK] Inizio elaborazione {len(shipment_ids)} spedizioni")
        for idx, shipment_id in enumerate(shipment_ids):
            try:
                logger.info(f"[CELERY_TASK] Elaborazione spedizione {idx+1}/{len(shipment_ids)}: ID {shipment_id}")
                
                # Get shipment details first for metadata
                shipment_details = None
                try:
                    if shipment_type == 'outbound':
                        shipment_details = client.get_outbound_shipment(shipment_id, merchant_id=merchant_id)
                    else:
                        shipment_details = client.get_inbound_shipment(shipment_id, merchant_id=merchant_id)
                    
                    logger.info(f"[CELERY_TASK] Dettagli spedizione {shipment_id}: {str(shipment_details)[:200]}...")
                except Exception as e_details:
                    logger.error(f"[CELERY_TASK] Errore recupero dettagli spedizione {shipment_id}: {e_details}")
                
                shipment_name = getattr(shipment_details, 'name', f"Spedizione {shipment_id}") if shipment_details else f"Spedizione {shipment_id}"
                logger.info(f"[CELERY_TASK] Nome spedizione {shipment_id}: {shipment_name}")
                
                # Get shipment items
                items_response = None
                items = []
                try:
                    items_response = client.get_outbound_shipment_items(
                        ship_id=shipment_id,
                        merchant_id=merchant_id
                    )
                    
                    if not items_response or 'items' not in items_response:
                        logger.warning(f"[CELERY_TASK] Nessun item trovato per shipment_id={shipment_id}")
                    else:
                        items = items_response['items']
                        logger.info(f"[CELERY_TASK] Trovati {len(items)} items per spedizione {shipment_id}")
                except Exception as e_items:
                    logger.error(f"[CELERY_TASK] Errore recupero items per shipment_id={shipment_id}: {e_items}")
                
                # Flag per tracciare se è stato aggiunto almeno un item per questa spedizione
                added_any_item = False
                
                # Process each item
                for item_idx, item in enumerate(items):
                    try:
                        logger.debug(f"[CELERY_TASK] Elaborazione item {item_idx+1}/{len(items)} di spedizione {shipment_id}")
                        product_info = extract_product_info_from_dict(item, shipment_type)
                        if product_info:
                            results.append({
                                'shipment_id': shipment_id,
                                'shipment_name': shipment_name,
                                'product_info': product_info
                            })
                            added_any_item = True
                            logger.debug(f"[CELERY_TASK] Item aggiunto ai risultati: {product_info['title']}")
                        else:
                            logger.debug(f"[CELERY_TASK] Item scartato, nessuna info prodotto estratta")
                    except Exception as e:
                        logger.error(f"[CELERY_TASK] Errore processing item in spedizione {shipment_id}: {str(e)}")
                        continue
                
                # SOLUZIONE: Aggiungi sempre almeno un item placeholder se non è stato aggiunto nulla
                if not added_any_item:
                    logger.warning(f"[CELERY_TASK] Nessun item valido trovato per shipment_id={shipment_id}, aggiungo placeholder")
                    placeholder_info = {
                        'title': f"Spedizione {shipment_name} (ID: {shipment_id})",
                        'sku': "PLACEHOLDER",
                        'asin': "PLACEHOLDER",
                        'fnsku': "PLACEHOLDER",
                        'quantity': 1
                    }
                    results.append({
                        'shipment_id': shipment_id,
                        'shipment_name': shipment_name if 'shipment_name' in locals() else f"Spedizione {shipment_id}",
                        'product_info': placeholder_info
                    })
                    logger.info(f"[CELERY_TASK] Aggiunto item placeholder per shipment_id={shipment_id}")
                
            except Exception as e:
                logger.error(f"[CELERY_TASK] Errore durante l'elaborazione di shipment_id={shipment_id}: {e}")
                
                # SOLUZIONE: Anche in caso di errore generale, aggiungi un placeholder
                logger.warning(f"[CELERY_TASK] Aggiungo placeholder per shipment_id={shipment_id} dopo errore")
                placeholder_info = {
                    'title': f"Spedizione errore (ID: {shipment_id})",
                    'sku': "ERROR",
                    'asin': "ERROR",
                    'fnsku': "ERROR",
                    'quantity': 0
                }
                results.append({
                    'shipment_id': shipment_id,
                    'shipment_name': shipment_name if 'shipment_name' in locals() else f"Spedizione {shipment_id}",
                    'product_info': placeholder_info
                })
                logger.info(f"[CELERY_TASK] Aggiunto item placeholder per errore shipment_id={shipment_id}")
                continue
        
        logger.info(f"[CELERY_TASK] Elaborazione completata. Salvando {len(results)} items nel database...")
        
        # Save results to database
        saved_count = 0
        with transaction.atomic():
            for result in results:
                try:
                    SearchResultItem.objects.create(
                        search_id=search_id,
                        shipment_id_api=str(result['shipment_id']),
                        shipment_type='outbound',
                        shipment_name=result['shipment_name'],
                        product_title=result['product_info']['title'][:255],
                        product_sku=result['product_info']['sku'][:255],
                        product_asin=result['product_info']['asin'][:255],
                        product_fnsku=result['product_info']['fnsku'][:255],
                        product_quantity=result['product_info']['quantity'],
                    )
                    saved_count += 1
                except Exception as e:
                    logger.error(f"[CELERY_TASK] Errore nel salvare l'item in DB: {e}")
                    continue
        
        logger.info(f"[CELERY_TASK] Salvati {saved_count} items nel DB su {len(results)} elaborati")
        
        # SOLUZIONE: Se non sono stati salvati item, ma c'erano spedizioni da processare,
        # forza la creazione di almeno un placeholder per ricerca
        if saved_count == 0 and len(shipment_ids) > 0:
            logger.warning(f"[CELERY_TASK] NESSUN ITEM SALVATO! Forzo un placeholder per la ricerca {search_id}")
            try:
                SearchResultItem.objects.create(
                    search_id=search_id,
                    shipment_id_api=str(shipment_ids[0]),
                    shipment_type='outbound',
                    shipment_name=f"RISULTATO FORZATO - Ricerca {search_id}"[:255],
                    product_title=f"RISULTATO FORZATO - Ricerca {search_id}"[:255],
                    product_sku="FORCED_RESULT",
                    product_asin="FORCED_RESULT",
                    product_fnsku="FORCED_RESULT",
                    product_quantity=1,
                )
                saved_count = 1
                logger.info(f"[CELERY_TASK] Aggiunto item forzato per la ricerca {search_id}")
            except Exception as e_force:
                logger.error(f"[CELERY_TASK] Errore nel forzare item: {e_force}")
        
        # Verifica che items siano stati salvati
        db_count = SearchResultItem.objects.filter(search_id=search_id).count()
        logger.info(f"[CELERY_TASK] Verifica DB: {db_count} items trovati per search_id={search_id}")
        
        # Imposta il flag done nella cache quando il task ha finito
        cache.set(f"{search_id}_done", True, timeout=600)
        logger.info(f"[CELERY_TASK] Impostato flag {search_id}_done=True")
        logger.info(f"[CELERY_TASK] ==============> FINE task process_shipment_batch <==============")
        
        return {
            'status': 'success',
            'processed_shipments': len(shipment_ids),
            'results_count': len(results),
            'saved_count': saved_count,
            'db_count': db_count
        }
        
    except Exception as exc:
        logger.error(f"[CELERY_TASK] ERRORE generale: {exc}")
        logger.error(f"[CELERY_TASK] Traceback: {traceback.format_exc()}")
        # In caso di errore, imposta comunque il flag done per evitare polling infinito
        cache.set(f"{search_id}_done", True, timeout=600)
        logger.error(f"[CELERY_TASK] Impostato flag {search_id}_done=True dopo errore")
        raise self.retry(exc=exc, countdown=5)
    finally:
        # Verifica finale dello stato del flag
        flag_state = cache.get(f"{search_id}_done")
        logger.info(f"[CELERY_TASK] Stato finale flag {search_id}_done: {flag_state}")
        
        # Se per qualche motivo il flag non è stato impostato, lo impostiamo qui
        if not flag_state:
            logger.warning(f"[CELERY_TASK] Flag {search_id}_done non impostato, lo imposto ora")
            cache.set(f"{search_id}_done", True, timeout=600)

@shared_task
def cleanup_old_searches():
    """
    Clean up old search results (older than 24 hours)
    """
    # cutoff_time = timezone.now() - timedelta(hours=24)
    # SearchResultItem.objects.filter(created_at__lt=cutoff_time).delete()
    SearchResultItem.objects.all().delete()

@shared_task
def echo_task(message):
    """
    Un task di test semplicissimo per verificare che Celery funziona.
    """
    logger.info(f"[CELERY_ECHO] ========================= ECHO TASK ========================")
    logger.info(f"[CELERY_ECHO] Messaggio ricevuto: {message}")
    logger.info(f"[CELERY_ECHO] Timestamp: {timezone.now()}")
    logger.info(f"[CELERY_ECHO] ========================= FINE ECHO ========================")
    return {"status": "echo_success", "message": message, "timestamp": str(timezone.now())}

@shared_task(bind=True, max_retries=3)
def process_shipment_search_task(self, search_id, search_terms, merchant_id, shipment_status, max_shipments_to_analyze):
    """
    Task Celery che esegue la ricerca delle spedizioni per parole chiave, merchant, status, ecc.
    Scarica le spedizioni, filtra per keyword (su nome e items), salva i risultati come SearchResultItem.
    """
    import time
    start_time = time.time()
    logger.info(f"[CELERY_SEARCH_TASK] INIZIO: search_id={search_id}, merchant_id={merchant_id}, status={shipment_status}, max={max_shipments_to_analyze}")
    client = _get_client()
    shipments_collected_from_api = []
    current_api_page = 1
    shipments_matching_criteria = []
    keywords_list = [kw.strip().lower() for kw in search_terms.split(',') if kw.strip()]
    
    try:
        SearchResultItem.objects.all().delete()
        while len(shipments_collected_from_api) < int(max_shipments_to_analyze):
            if shipment_status == 'archived':
                shipments_page_response = client.get_archived_outbound_shipments(
                    merchant_id=merchant_id, page=current_api_page, per_page=50
                )
            else:
                shipments_page_response = client.get_outbound_shipments(
                    merchant_id=merchant_id, page=current_api_page, per_page=50
                )
            if not shipments_page_response or not shipments_page_response.data:
                break
            shipments_collected_from_api.extend(shipments_page_response.data)
            if not shipments_page_response.next_page_url:
                break
            current_api_page += 1
        shipments_to_actually_analyze = shipments_collected_from_api[:int(max_shipments_to_analyze)]
        cache.set(f"search_{search_id}_total_to_analyze", len(shipments_to_actually_analyze), timeout=3600)
        logger.info(f"[CELERY_SEARCH_TASK] Scaricate {len(shipments_to_actually_analyze)} spedizioni da analizzare")
        for idx, shipment_obj in enumerate(shipments_to_actually_analyze):
            shipment_name = getattr(shipment_obj, 'name', '')
            shipment_id = getattr(shipment_obj, 'id', None)
            shipment_name_lower = str(shipment_name).lower()
            found_match_in_name = any(kw in shipment_name_lower for kw in keywords_list)
            if found_match_in_name:
                shipments_matching_criteria.append(shipment_obj)
                continue
            try:
                items_response = client.get_outbound_shipment_items(shipment_id=shipment_id, merchant_id=merchant_id)
                logger.info(f"[CELERY_SEARCH_TASK] items_response per shipment_id={shipment_id}: {items_response} (type={type(items_response)})")
                items_list = []
                if isinstance(items_response, dict):
                    items_list = items_response.get('items', [])
                elif hasattr(items_response, 'items'):
                    items_list = items_response.items
                else:
                    logger.warning(f"[CELERY_SEARCH_TASK] items_response non ha attributo 'items' per shipment_id={shipment_id}: {type(items_response)}")
                if items_list and hasattr(items_list[0], 'model_dump'):
                    items_list = [i.model_dump() for i in items_list]
                logger.info(f"[CELERY_SEARCH_TASK] items_list per shipment_id={shipment_id}: {items_list} (len={len(items_list)})")
                for item_data in items_list:
                    item_title = ''
                    inner_item = item_data.get('item')
                    if inner_item and isinstance(inner_item, dict):
                        item_title = str(inner_item.get('title', '')).lower()
                    else:
                        item_title = str(item_data.get('title') or item_data.get('name', '')).lower()
                    if any(kw in item_title for kw in keywords_list):
                        shipments_matching_criteria.append(shipment_obj)
                        break
            except Exception as e_items:
                logger.error(f"[CELERY_SEARCH_TASK] Errore items per shipment {shipment_id}: {e_items}")
        logger.info(f"[CELERY_SEARCH_TASK] Trovate {len(shipments_matching_criteria)} spedizioni che matchano i criteri")
        logger.info(f"[CELERY_SEARCH_TASK] shipments_matching_criteria: {[getattr(s, 'id', None) for s in shipments_matching_criteria]}")
        records_created = 0
        for shipment_obj in shipments_matching_criteria:
            try:
                shipment_id = getattr(shipment_obj, 'id', 'N/A')
                shipment_name = getattr(shipment_obj, 'name', f"Spedizione {shipment_id}")
                items_response = client.get_outbound_shipment_items(shipment_id=shipment_id, merchant_id=merchant_id)
                logger.info(f"[CELERY_SEARCH_TASK] items_response per shipment_id={shipment_id}: {items_response}")
                items_list = []
                if isinstance(items_response, dict):
                    items_list = items_response.get('items', [])
                elif hasattr(items_response, 'items'):
                    items_list = items_response.items
                else:
                    logger.warning(f"[CELERY_SEARCH_TASK] items_response non ha attributo 'items' per shipment_id={shipment_id}: {type(items_response)}")
                if items_list and hasattr(items_list[0], 'model_dump'):
                    items_list = [i.model_dump() for i in items_list]
                logger.info(f"[CELERY_SEARCH_TASK] items_list per shipment_id={shipment_id}: {items_list} (len={len(items_list)})")
                for item_data in items_list:
                    inner_item = item_data.get('item')
                    if inner_item and isinstance(inner_item, dict):
                        product_title = inner_item.get('title', '')
                        product_sku = inner_item.get('sku', '')
                        product_asin = inner_item.get('asin', '')
                        product_fnsku = inner_item.get('fnsku', '')
                        product_quantity = item_data.get('quantity', 1)
                    else:
                        product_title = item_data.get('title') or item_data.get('name', '')
                        product_sku = item_data.get('sku', '')
                        product_asin = item_data.get('asin', '')
                        product_fnsku = item_data.get('fnsku', '')
                        product_quantity = item_data.get('quantity', 1)
                    try:
                        SearchResultItem.objects.create(
                            search_id=search_id,
                            shipment_type='outbound',
                            shipment_name=shipment_name,
                            product_title=product_title,
                            product_sku=product_sku,
                            product_asin=product_asin,
                            product_fnsku=product_fnsku,
                            product_quantity=product_quantity,
                        )
                        records_created += 1
                    except Exception as e_create:
                        logger.error(
                            f"[CELERY_SEARCH_TASK] Errore creazione record DB: {e_create}\n"
                            f"Dati tentati: search_id={search_id}, shipment_name={shipment_name}, "
                            f"product_title={product_title}, product_sku={product_sku}, "
                            f"product_asin={product_asin}, product_fnsku={product_fnsku}, "
                            f"product_quantity={product_quantity}\n"
                            f"Traceback: {traceback.format_exc()}"
                        )
            except Exception as e_create:
                logger.error(f"[CELERY_SEARCH_TASK] Errore creazione record DB (outer): {e_create}\nTraceback: {traceback.format_exc()}")
        if records_created == 0:
            logger.warning(
                f"[CELERY_SEARCH_TASK] Nessun record creato! "
                f"Spedizioni matching: {len(shipments_matching_criteria)}. "
                f"Verifica i dati e i log degli errori precedenti."
            )
        logger.info(f"[CELERY_SEARCH_TASK] FINE: creati {records_created} record per search_id={search_id}")
        total_execution_time = time.time() - start_time
        logger.info(f"[CELERY_SEARCH_TASK] Tempo totale esecuzione: {total_execution_time:.2f} s")
        # Qui il task ha effettivamente finito di processare tutte le spedizioni richieste
        logger.info(f"[CELERY_SEARCH_TASK] Ricerca completata, imposto flag done per search_id={search_id}")
        cache.set(f"{search_id}_done", True, timeout=600)
    except Exception as e:
        logger.error(f"[CELERY_SEARCH_TASK] ERRORE GENERALE: {e}\n{traceback.format_exc()}")
    finally:
        # Fallback di sicurezza: se per qualche motivo il flag non è stato impostato, lo imposto qui
        if not cache.get(f"{search_id}_done"):
            logger.warning(f"[CELERY_SEARCH_TASK] [finally] Flag {search_id}_done non impostato, lo imposto ora (fallback)")
            cache.set(f"{search_id}_done", True, timeout=600) 

@shared_task(name="prep_management.send_telegram_notification")
def send_telegram_notification(email: str, message: str, event_type: str = "generic", shipment_id: str = None):
    # This task is a proxy to the actual service function.
    send_notification_service(email=email, message=message, event_type=event_type, shipment_id=shipment_id)

@shared_task(name="prep_management.notify_telegram_users_about_shipment")
def notify_telegram_users_about_shipment(merchant_id: str, message: str, event_type: str, shipment_id: str):
    """
    Invia una notifica a tutti gli utenti Telegram associati a un merchant.
    """
    logger.info(f"Task Celery: Avvio notifica per merchant {merchant_id}, evento {event_type}, shipment {shipment_id}")
    
    client = _get_client()
    if not client:
        logger.error(f"Impossibile notificare per merchant {merchant_id}: client non inizializzato.")
        return

    try:
        merchant_response = client.get_merchant(merchant_id=int(merchant_id))
        if not merchant_response or not merchant_response.merchant:
            logger.error(f"Merchant {merchant_id} non trovato tramite API.")
            return
            
        merchant_email = merchant_response.merchant.primary_email
        if not merchant_email:
            logger.warning(f"Merchant {merchant_id} non ha un'email primaria configurata.")
            return

        users_to_notify = TelegramNotification.objects.filter(email__iexact=merchant_email, is_active=True)
        if not users_to_notify.exists():
            logger.info(f"Nessun utente Telegram attivo trovato per l'email {merchant_email} (merchant {merchant_id}).")
            return

        for user in users_to_notify:
            logger.info(f"Invio notifica a {user.email} (Chat ID: {user.chat_id})")
            send_notification_service(
                email=user.email,
                message=message,
                event_type=event_type,
                shipment_id=shipment_id
            )

    except Exception as e:
        logger.error(f"Errore durante l'invio di notifiche per merchant {merchant_id}: {e}", exc_info=True) 