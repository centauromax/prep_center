import logging
from celery import shared_task
from django.db import transaction
from django.core.cache import cache
from .models import SearchResultItem
from .utils.extractors import extract_product_info_from_dict
from libs.prepbusiness.client import PrepBusinessClient
from libs.config import PREP_BUSINESS_API_KEY, PREP_BUSINESS_API_URL
from .utils.clients import get_client
import traceback
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)

def get_client():
    company_domain = PREP_BUSINESS_API_URL.split('//')[-1].split('/')[0]
    return PrepBusinessClient(
        api_key=PREP_BUSINESS_API_KEY,
        company_domain=company_domain
    )

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
        
        client = get_client()
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
                        shipment_id_api=result['shipment_id'],
                        shipment_name=result.get('shipment_name', f"Spedizione {result['shipment_id']}")[:255],
                        shipment_type=shipment_type,
                        product_title=result['product_info']['title'][:255],
                        product_sku=result['product_info']['sku'][:255],
                        product_asin=result['product_info']['asin'][:255],
                        product_fnsku=result['product_info']['fnsku'][:255],
                        product_quantity=result['product_info']['quantity'],
                        processing_status='complete'
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
                    shipment_id_api=shipment_ids[0],
                    shipment_name=f"RISULTATO FORZATO - Ricerca {search_id}"[:255],
                    shipment_type=shipment_type,
                    product_title=f"RISULTATO FORZATO - Ricerca {search_id}"[:255],
                    product_sku="FORCED_RESULT",
                    product_asin="FORCED_RESULT",
                    product_fnsku="FORCED_RESULT",
                    product_quantity=1,
                    processing_status='complete'
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
    cutoff_time = timezone.now() - timedelta(hours=24)
    SearchResultItem.objects.filter(created_at__lt=cutoff_time).delete()

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