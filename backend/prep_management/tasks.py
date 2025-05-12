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

logger = logging.getLogger(__name__)

def get_client():
    company_domain = PREP_BUSINESS_API_URL.split('//')[-1].split('/')[0]
    return PrepBusinessClient(
        api_key=PREP_BUSINESS_API_KEY,
        company_domain=company_domain
    )

@shared_task(bind=True, max_retries=3)
def process_shipment_batch(self, search_id, shipment_ids, merchant_id, shipment_type='outbound'):
    logger.info(f"[CELERY_TASK] Inizio task process_shipment_batch - search_id={search_id}, shipment_ids={shipment_ids}, merchant_id={merchant_id}")
    logger.info(f"[CELERY_TASK] Task ID: {self.request.id}")
    logger.info(f"[CELERY_TASK] Stato task: {self.request.state}")
    
    try:
        # Imposta il flag a False all'inizio
        cache.set(f"{search_id}_done", False, timeout=600)
        logger.info(f"[CELERY_TASK] Impostato flag {search_id}_done=False all'inizio del task")
        
        # Recupera le spedizioni dal database
        shipments = Shipment.objects.filter(id__in=shipment_ids)
        logger.info(f"[CELERY_TASK] Recuperate {len(shipments)} spedizioni dal database")
        
        # Se non ci sono spedizioni, termina subito
        if not shipments.exists():
            logger.warning("[CELERY_TASK] Nessuna spedizione trovata nel database")
            cache.set(f"{search_id}_done", True, timeout=600)
            logger.info(f"[CELERY_TASK] Impostato flag {search_id}_done=True (nessuna spedizione trovata)")
            return
        
        # Prepara i dati per l'API
        shipments_data = []
        for shipment in shipments:
            try:
                shipment_data = prepare_shipment_data(shipment, merchant_id)
                if shipment_data:
                    shipments_data.append(shipment_data)
                    logger.debug(f"[CELERY_TASK] Preparati dati per spedizione {shipment.id}")
            except Exception as e:
                logger.error(f"[CELERY_TASK] Errore nella preparazione dati spedizione {shipment.id}: {e}")
                continue
        
        logger.info(f"[CELERY_TASK] Preparati {len(shipments_data)} spedizioni per l'API")
        
        if not shipments_data:
            logger.warning("[CELERY_TASK] Nessuna spedizione valida da processare")
            cache.set(f"{search_id}_done", True, timeout=600)
            logger.info(f"[CELERY_TASK] Impostato flag {search_id}_done=True (nessuna spedizione valida)")
            return
        
        # Invia i dati all'API
        try:
            logger.info("[CELERY_TASK] Invio dati all'API Prep Business")
            response = send_shipments_to_prep_business(shipments_data, merchant_id)
            logger.info(f"[CELERY_TASK] Risposta API: {response}")
        except Exception as e:
            logger.error(f"[CELERY_TASK] Errore nell'invio dati all'API: {e}")
            raise
        
        # Imposta il flag a True alla fine
        cache.set(f"{search_id}_done", True, timeout=600)
        logger.info(f"[CELERY_TASK] Impostato flag {search_id}_done=True alla fine del task")
        
    except Exception as e:
        logger.error(f"[CELERY_TASK] Errore nel task: {e}")
        logger.error(f"[CELERY_TASK] Traceback: {traceback.format_exc()}")
        # In caso di errore, imposta comunque il flag a True
        cache.set(f"{search_id}_done", True, timeout=600)
        logger.info(f"[CELERY_TASK] Impostato flag {search_id}_done=True dopo errore")
        # Ritenta il task
        raise self.retry(exc=e, countdown=5)
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
    from django.utils import timezone
    from datetime import timedelta
    
    cutoff_time = timezone.now() - timedelta(hours=24)
    SearchResultItem.objects.filter(created_at__lt=cutoff_time).delete() 