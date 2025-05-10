import logging
from celery import shared_task
from django.db import transaction
from .models import SearchResultItem
from .utils.extractors import extract_product_info_from_dict
from .clients import get_client

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def process_shipment_batch(self, search_id, shipment_ids, merchant_id, page=1, shipment_type='outbound'):
    """
    Process a batch of shipments asynchronously
    """
    try:
        client = get_client()
        results = []
        
        for shipment_id in shipment_ids:
            try:
                # Get shipment items
                items_response = client.get_outbound_shipment_items(
                    ship_id=shipment_id,
                    merchant_id=merchant_id
                )
                
                if not items_response or 'items' not in items_response:
                    logger.warning(f"No items found for shipment {shipment_id}")
                    continue
                
                items = items_response['items']
                logger.info(f"Found {len(items)} items for shipment {shipment_id}")
                
                # Process each item
                for item in items:
                    try:
                        product_info = extract_product_info_from_dict(item, shipment_type)
                        if product_info:
                            results.append({
                                'shipment_id': shipment_id,
                                'product_info': product_info
                            })
                    except Exception as e:
                        logger.error(f"Error processing item in shipment {shipment_id}: {str(e)}")
                        continue
                
            except Exception as e:
                logger.error(f"Error processing shipment {shipment_id}: {str(e)}")
                continue
        
        # Save results to database
        with transaction.atomic():
            for result in results:
                SearchResultItem.objects.create(
                    search_id=search_id,
                    shipment_id=result['shipment_id'],
                    title=result['product_info']['title'],
                    sku=result['product_info']['sku'],
                    asin=result['product_info']['asin'],
                    fnsku=result['product_info']['fnsku'],
                    quantity=result['product_info']['quantity'],
                    processing_status='completed'
                )
        
        return {
            'status': 'success',
            'processed_shipments': len(shipment_ids),
            'results_count': len(results)
        }
        
    except Exception as e:
        logger.error(f"Error in process_shipment_batch: {str(e)}")
        self.retry(exc=e, countdown=60)  # Retry after 1 minute

@shared_task
def cleanup_old_searches():
    """
    Clean up old search results (older than 24 hours)
    """
    from django.utils import timezone
    from datetime import timedelta
    
    cutoff_time = timezone.now() - timedelta(hours=24)
    SearchResultItem.objects.filter(created_at__lt=cutoff_time).delete() 