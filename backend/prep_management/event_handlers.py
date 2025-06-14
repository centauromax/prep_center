import logging
from typing import Dict, Any, Optional
from django.utils import timezone

# Import diretto del client ufficiale e dei suoi modelli
from libs.prepbusiness.client import PrepBusinessClient
from libs.prepbusiness.models import InboundShipmentCreate, InboundShipmentItemCreate

from .models import ShipmentStatusUpdate, PrepBusinessConfig
from .services import format_shipment_notification
from .tasks import queue_telegram_notification

logger = logging.getLogger(__name__)

class WebhookEventProcessor:
    """
    Elabora gli eventi webhook usando ESCLUSIVAMENTE il client ufficiale.
    Nessun wrapper, nessuna logica di fallback. Una sola fonte di verità.
    """
    def __init__(self):
        self.client = self._initialize_client()
        if self.client:
            logger.info("WebhookEventProcessor: Client Ufficiale PrepBusiness inizializzato correttamente.")
        else:
            logger.error("ERRORE CRITICO: WebhookEventProcessor non è riuscito a inizializzare il client ufficiale.")

    def _initialize_client(self) -> Optional[PrepBusinessClient]:
        """Inizializza il client ufficiale leggendo la config dal DB o dalle variabili d'ambiente."""
        try:
            config = PrepBusinessConfig.objects.filter(is_active=True).first()
            if config and config.api_url and config.api_key:
                logger.info("Inizializzazione client da configurazione DB.")
                domain = config.api_url.replace('https://', '').split('/api')[0]
                return PrepBusinessClient(api_key=config.api_key, company_domain=domain, timeout=config.api_timeout)
            
            logger.warning("Configurazione DB non trovata. Fallback su variabili d'ambiente.")
            from libs.config import PREP_BUSINESS_API_URL, PREP_BUSINESS_API_KEY, PREP_BUSINESS_API_TIMEOUT
            if PREP_BUSINESS_API_KEY and PREP_BUSINESS_API_URL:
                domain = PREP_BUSINESS_API_URL.replace('https://', '').split('/api')[0]
                return PrepBusinessClient(api_key=PREP_BUSINESS_API_KEY, company_domain=domain, timeout=PREP_BUSINESS_API_TIMEOUT)
            
            logger.error("Nessuna configurazione API valida trovata (né DB, né .env). Client non creato.")
            return None
        except Exception as e:
            logger.error(f"Errore critico durante l'inizializzazione del client: {e}", exc_info=True)
            return None

    def process_event(self, update_id: int) -> Dict[str, Any]:
        """Punto di ingresso per l'elaborazione di un evento."""
        try:
            update = ShipmentStatusUpdate.objects.get(id=update_id)
        except ShipmentStatusUpdate.DoesNotExist:
            return {'success': False, 'message': f'Update {update_id} non trovato.'}

        if not self.client:
            return {'success': False, 'message': 'Client non disponibile. Elaborazione annullata.'}

        event_type = update.event_type
        logger.info(f"Inizio elaborazione: ID={update.id}, Tipo={event_type}, ShipmentID={update.shipment_id}")

        processing_map = {
            'outbound_shipment.created': self._process_outbound_shipment_created,
            'outbound_shipment.closed': self._process_outbound_shipment_closed,
        }
        handler = processing_map.get(event_type, self._process_default_event)
        
        result = handler(update)

        self._send_telegram_notification_if_needed(update, result)

        update.processed = True
        update.process_success = result.get('success', False)
        update.processing_result = result
        update.processed_at = timezone.now()
        update.save()
        
        logger.info(f"Fine elaborazione ID={update.id}. Successo: {update.process_success}")
        return result

    def _process_default_event(self, update: ShipmentStatusUpdate) -> Dict[str, Any]:
        """Gestisce eventi per cui non c'è una logica specifica."""
        logger.info(f"Evento '{update.event_type}' gestito di default.")
        return {'success': True, 'message': f'Evento {update.event_type} ricevuto.'}

    def _process_outbound_shipment_created(self, update: ShipmentStatusUpdate) -> Dict[str, Any]:
        """Verifica se per un outbound appena creato esiste un inbound corrispondente."""
        data = update.payload.get('data', {})
        shipment_name = str(data.get('name', ''))
        merchant_id = int(data.get('team_id'))

        try:
            inbound_response = self.client.get_inbound_shipments(merchant_id=merchant_id, per_page=500, status='open')
            active_inbounds = inbound_response.shipments if inbound_response else []
            
            matching_shipment = next((s for s in active_inbounds if s.name.lower() == shipment_name.lower()), None)
            
            if matching_shipment:
                msg = f"Trovata corrispondenza inbound: ID {matching_shipment.id}"
                logger.info(msg)
                return {'success': True, 'message': msg}
            else:
                msg = f"Nessuna corrispondenza inbound trovata per '{shipment_name}'"
                logger.warning(msg)
                return {'success': True, 'message': msg, 'status': 'no_inbound_match'}
        except Exception as e:
            logger.error(f"Errore in _process_outbound_shipment_created: {e}", exc_info=True)
            return {'success': False, 'message': str(e)}

    def _process_outbound_shipment_closed(self, update: ShipmentStatusUpdate) -> Dict[str, Any]:
        """Calcola i residuali quando un outbound viene chiuso."""
        data = update.payload.get('data', {})
        outbound_id = int(data.get('id'))
        shipment_name = str(data.get('name', ''))
        merchant_id = int(data.get('team_id'))

        try:
            outbound_items_resp = self.client.get_outbound_shipment_items(shipment_id=outbound_id, merchant_id=merchant_id)
            outbound_items = [i.model_dump() for i in outbound_items_resp.items] if outbound_items_resp else []
            logger.info(f"Recuperati {len(outbound_items)} items da outbound {outbound_id}")

            inbound_resp = self.client.get_inbound_shipments(merchant_id=merchant_id, name=shipment_name, per_page=1)
            if not (inbound_resp and inbound_resp.shipments):
                return {'success': True, 'message': f"Nessun inbound corrispondente a '{shipment_name}' trovato."}
            
            inbound_original_model = inbound_resp.shipments[0]
            inbound_original_id = inbound_original_model.id
            
            inbound_items_resp = self.client.get_inbound_shipment_items(shipment_id=inbound_original_id, merchant_id=merchant_id)
            inbound_items = [i.model_dump() for i in inbound_items_resp.items] if inbound_items_resp else []
            logger.info(f"Recuperati {len(inbound_items)} items da inbound originale {inbound_original_id}")

            residual_items_data = self._calculate_residual_items(inbound_items, outbound_items)
            if not residual_items_data:
                return {'success': True, 'message': 'Nessun item residuale da creare.'}
            
            logger.info(f"Calcolati {len(residual_items_data)} items residuali.")

            residual_name = f"{shipment_name} - RESIDUAL"
            
            items_to_create = [InboundShipmentItemCreate(**item_data) for item_data in residual_items_data]
            
            shipment_to_create = InboundShipmentCreate(
                name=residual_name,
                warehouse_id=inbound_original_model.warehouse_id,
                merchant_id=merchant_id,
                items=items_to_create,
                notes=f"Creato automaticamente da outbound {outbound_id}"
            )
            
            # Qui usiamo il metodo corretto del client completo
            new_shipment_resp = self.client.create_inbound_shipment(shipment_data=shipment_to_create)
            
            if new_shipment_resp and new_shipment_resp.shipment:
                msg = f"Creato inbound residuale ID {new_shipment_resp.shipment.id}"
                return {'success': True, 'message': msg, 'residual_shipment_id': new_shipment_resp.shipment.id}
            else:
                raise Exception("La creazione dell'inbound residuale non ha restituito un ID valido.")

        except Exception as e:
            logger.error(f"Errore in _process_outbound_shipment_closed: {e}", exc_info=True)
            return {'success': False, 'message': str(e)}

    def _calculate_residual_items(self, inbound_items: list, outbound_items: list) -> list:
        outbound_sku_map = {item.get('sku'): item.get('quantity', 0) for item in outbound_items}
        residual_items = []
        for item in inbound_items:
            shipped_qty = outbound_sku_map.get(item.get('sku'), 0)
            original_qty = item.get('quantity', 0) or item.get('actual_quantity', 0)

            residual_qty = original_qty - shipped_qty
            if residual_qty > 0:
                residual_data = {
                    "sku": item.get('sku'), "quantity": residual_qty, "name": item.get('name'),
                    "asin": item.get('asin'), "fnsku": item.get('fnsku'), "photo_url": item.get('photo_url'),
                }
                residual_items.append(residual_data)
        return residual_items

    def _send_telegram_notification_if_needed(self, update: ShipmentStatusUpdate, result: Dict[str, Any]):
        notify_events = ['inbound_shipment.created', 'inbound_shipment.received', 'outbound_shipment.created', 'outbound_shipment.closed']
        if update.event_type not in notify_events: return

        try:
            merchant_email = self._get_merchant_email(update.merchant_id)
            if not merchant_email:
                logger.warning(f"Email per merchant {update.merchant_id} non trovata. Notifica saltata.")
                return
            
            message = format_shipment_notification(update.event_type, update.payload, result)
            
            queue_telegram_notification(email=merchant_email, message=message, event_type=update.event_type, shipment_id=update.shipment_id)
            logger.info(f"Notifica Telegram per merchant {update.merchant_id} accodata con successo.")
        except Exception as e:
            logger.error(f"Errore durante l'accodamento della notifica Telegram: {e}", exc_info=True)

    def _get_merchant_email(self, merchant_id: str) -> Optional[str]:
        try:
            merchant_resp = self.client.get_merchant(merchant_id=int(merchant_id))
            if merchant_resp and merchant_resp.merchant:
                return merchant_resp.merchant.primary_email
        except Exception as e:
            logger.error(f"Impossibile recuperare email per merchant {merchant_id}: {e}")
        return None 