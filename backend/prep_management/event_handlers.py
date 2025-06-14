import logging
from typing import Dict, Any, Optional
from django.utils import timezone

# Import diretto del client ufficiale
from libs.prepbusiness.client import PrepBusinessClient
from libs.prepbusiness.models import PrepBusinessError, AuthenticationError

from .models import ShipmentStatusUpdate, PrepBusinessConfig
from .services import format_shipment_notification
from .tasks import send_telegram_notification

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
            inbound_response = self.client.get_inbound_shipments(merchant_id=merchant_id, per_page=500)
            active_inbounds = inbound_response.data if inbound_response else []
            
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
        """Calcola i residuali e partial quando un outbound viene chiuso."""
        data = update.payload.get('data', {})
        outbound_id = int(data.get('id'))
        shipment_name = str(data.get('name', ''))
        merchant_id = int(data.get('team_id'))

        try:
            # 1. Recupero items dall'outbound chiuso
            outbound_items_resp = self.client.get_outbound_shipment_items(shipment_id=outbound_id, merchant_id=merchant_id)
            outbound_items = [i.model_dump() for i in outbound_items_resp.items] if outbound_items_resp and outbound_items_resp.items else []
            logger.info(f"Recuperati {len(outbound_items)} items da outbound {outbound_id}")

            # 2. Cerco l'inbound originale corrispondente
            inbound_resp = self.client.get_inbound_shipments(merchant_id=merchant_id, per_page=500)
            if not (inbound_resp and inbound_resp.data):
                return {'success': True, 'message': f"Nessun inbound trovato per merchant {merchant_id}."}
            
            # Filtra per nome
            matching_inbounds = [s for s in inbound_resp.data if s.name.lower() == shipment_name.lower()]
            if not matching_inbounds:
                return {'success': True, 'message': f"Nessun inbound corrispondente a '{shipment_name}' trovato."}
            
            inbound_original_model = matching_inbounds[0]
            inbound_original_id = inbound_original_model.id
            
            # 3. Recupero items dall'inbound originale
            inbound_items_resp = self.client.get_inbound_shipment_items(shipment_id=inbound_original_id, merchant_id=merchant_id)
            inbound_items = [i.model_dump() for i in inbound_items_resp.items] if inbound_items_resp and inbound_items_resp.items else []
            logger.info(f"Recuperati {len(inbound_items)} items da inbound originale {inbound_original_id}")

            # 4. Calcolo residuali e partial
            residual_items_data = self._calculate_residual_items(inbound_items, outbound_items)
            partial_items_data = self._calculate_partial_items(inbound_items, outbound_items)
            
            # Determina quale tipo di spedizione creare
            create_residual = len(residual_items_data) > 0
            create_partial = len(partial_items_data) > 0 and not create_residual  # Partial solo se non ci sono residual
            
            if not create_residual and not create_partial:
                return {'success': True, 'message': 'Nessun item residuale o partial da creare.'}
            
            # 5. Crea la spedizione appropriata
            if create_residual:
                logger.info(f"Calcolati {len(residual_items_data)} items residuali.")
                items_to_create = residual_items_data
                shipment_suffix = "RESIDUAL"
                creation_type = "residuale"
            else:  # create_partial
                logger.info(f"Calcolati {len(partial_items_data)} items partial.")
                items_to_create = partial_items_data
                shipment_suffix = "PARTIAL"
                creation_type = "partial"
            
            new_shipment_name = f"{shipment_name} - {shipment_suffix}"
            
            # Step 1: Crea lo shipment vuoto
            logger.info(f"Creo lo shipment {creation_type} vuoto con nome: {new_shipment_name}")
            created_shipment_resp = self.client.create_inbound_shipment(
                name=new_shipment_name,
                warehouse_id=inbound_original_model.warehouse_id,
                notes=f"Creato automaticamente da outbound {outbound_id}",
                merchant_id=merchant_id
            )
            shipment_id = created_shipment_resp.shipment_id
            logger.info(f"Shipment {creation_type} vuoto creato con ID: {shipment_id}")

            # Step 2: Aggiunge gli items uno a uno
            logger.info(f"Aggiungo {len(items_to_create)} items allo shipment {shipment_id}")
            for item in items_to_create:
                sku = item.get("sku")
                quantity = item.get("quantity")
                
                # Cerca l'item_id dallo SKU
                try:
                    inventory_resp = self.client.search_inventory(query=sku)
                    if inventory_resp and inventory_resp.items:
                        # Prende il primo item che corrisponde allo SKU
                        matching_item = next((i for i in inventory_resp.items if i.merchant_sku == sku), None)
                        if matching_item:
                            self.client.add_item_to_shipment(
                                shipment_id=shipment_id,
                                item_id=matching_item.id,
                                quantity=quantity,
                                merchant_id=merchant_id
                            )
                            logger.info(f"Aggiunto item SKU {sku} (ID: {matching_item.id}) con quantità {quantity}")
                        else:
                            logger.warning(f"Nessun item trovato per SKU {sku}")
                    else:
                        logger.warning(f"Nessun risultato dalla ricerca per SKU {sku}")
                except Exception as e:
                    logger.error(f"Errore durante l'aggiunta dell'item SKU {sku}: {e}")
                    
            logger.info(f"Tutti gli items sono stati aggiunti allo shipment {creation_type}.")
            
            msg = f"Creato inbound {creation_type} ID {shipment_id}"
            return {'success': True, 'message': msg, f'{creation_type}_shipment_id': shipment_id}

        except Exception as e:
            logger.error(f"Errore in _process_outbound_shipment_closed: {e}", exc_info=True)
            return {'success': False, 'message': str(e)}

    def _calculate_partial_items(self, inbound_items: list, outbound_items: list) -> list:
        """Calcola gli items partial (quantità uguali tra inbound e outbound)."""
        logger.info(f"--- Inizio Calcolo Partial (Log Dettagliato V1) ---")
        
        # Crea mappa SKU outbound - accede alla struttura annidata
        outbound_sku_map = {}
        for item in outbound_items:
            # OutboundShipmentItem ha: item.item.merchant_sku
            sku = None
            if 'item' in item and item['item']:
                sku = item['item'].get('merchant_sku')
            if not sku:
                # Fallback: cerca direttamente
                sku = item.get('sku') or item.get('merchant_sku')
            
            if sku:
                quantity = item.get('quantity', 0)
                outbound_sku_map[sku] = outbound_sku_map.get(sku, 0) + quantity
                logger.info(f"OUTBOUND SKU: {sku} → Quantità: {quantity}")
            else:
                logger.warning(f"Outbound item senza SKU valido: {item}")
        
        partial_items = []
        logger.info(f"MAPPA SKU OUTBOUND: {outbound_sku_map}")

        for item in inbound_items:
            # ShipmentItem ha: item.item.merchant_sku
            sku = None
            if 'item' in item and item['item']:
                sku = item['item'].get('merchant_sku')
            if not sku:
                # Fallback: cerca direttamente
                sku = item.get('sku') or item.get('merchant_sku')
            
            if not sku:
                logger.warning("Trovato item inbound senza SKU, verrà ignorato.")
                logger.debug(f"Item inbound senza SKU: {item}")
                continue

            shipped_qty = outbound_sku_map.get(sku, 0)
            
            # Logica robusta per la quantità inbound
            inbound_qty = 0
            
            # Prova con struttura annidata: item.actual.quantity, item.expected.quantity
            if 'actual' in item and item['actual']:
                inbound_qty = item['actual'].get('quantity', 0)
            elif 'expected' in item and item['expected']:
                inbound_qty = item['expected'].get('quantity', 0)
            else:
                # Fallback: cerca direttamente
                inbound_qty = item.get('actual_quantity')
                if inbound_qty is None:
                    inbound_qty = item.get('expected_quantity')
                if inbound_qty is None:
                    inbound_qty = item.get('quantity', 0)

            logger.info(f"SKU: {sku} | Q.Inbound: {inbound_qty} | Q.Spedita: {shipped_qty}")

            # Per i PARTIAL: quantità uguali (inbound = outbound) e > 0
            if inbound_qty > 0 and inbound_qty == shipped_qty:
                # Estrai altri dati dall'item annidato
                item_data = item.get('item', {}) if 'item' in item else item
                
                partial_data = {
                    "sku": sku,
                    "quantity": inbound_qty,  # Stessa quantità
                    "name": item_data.get('title') or item_data.get('name'),
                    "asin": item_data.get('asin'),
                    "fnsku": item_data.get('fnsku'),
                    "photo_url": item_data.get('photo_url'),
                }
                partial_items.append(partial_data)
                logger.info(f"  -> ✅ AGGIUNTO PARTIAL: SKU {sku} con quantità {inbound_qty}")
        
        logger.info(f"--- Fine Calcolo Partial: {len(partial_items)} items totali ---")
        return partial_items
        
    def _calculate_residual_items(self, inbound_items: list, outbound_items: list) -> list:
        """Calcola gli items residuali (quantità inbound > outbound) in modo robusto."""
        logger.info(f"--- Inizio Calcolo Residuali (Log Dettagliato V4) ---")
        
        # Crea mappa SKU outbound - accede alla struttura annidata
        outbound_sku_map = {}
        for item in outbound_items:
            # OutboundShipmentItem ha: item.item.merchant_sku
            sku = None
            if 'item' in item and item['item']:
                sku = item['item'].get('merchant_sku')
            if not sku:
                # Fallback: cerca direttamente
                sku = item.get('sku') or item.get('merchant_sku')
            
            if sku:
                quantity = item.get('quantity', 0)
                outbound_sku_map[sku] = outbound_sku_map.get(sku, 0) + quantity
                logger.info(f"OUTBOUND SKU: {sku} → Quantità: {quantity}")
            else:
                logger.warning(f"Outbound item senza SKU valido: {item}")
        
        residual_items = []
        logger.info(f"MAPPA SKU OUTBOUND: {outbound_sku_map}")

        for item in inbound_items:
            # ShipmentItem ha: item.item.merchant_sku
            sku = None
            if 'item' in item and item['item']:
                sku = item['item'].get('merchant_sku')
            if not sku:
                # Fallback: cerca direttamente
                sku = item.get('sku') or item.get('merchant_sku')
            
            if not sku:
                logger.warning("Trovato item inbound senza SKU, verrà ignorato.")
                logger.debug(f"Item inbound senza SKU: {item}")
                continue

            shipped_qty = outbound_sku_map.get(sku, 0)
            
            # Logica robusta per la quantità inbound
            inbound_qty = 0
            
            # Prova con struttura annidata: item.actual.quantity, item.expected.quantity
            if 'actual' in item and item['actual']:
                inbound_qty = item['actual'].get('quantity', 0)
            elif 'expected' in item and item['expected']:
                inbound_qty = item['expected'].get('quantity', 0)
            else:
                # Fallback: cerca direttamente
                inbound_qty = item.get('actual_quantity')
                if inbound_qty is None:
                    inbound_qty = item.get('expected_quantity')
                if inbound_qty is None:
                    inbound_qty = item.get('quantity', 0)

            residual_qty = inbound_qty - shipped_qty
            
            logger.info(f"SKU: {sku} | Q.Inbound: {inbound_qty} | Q.Spedita: {shipped_qty} | ==> RESIDUALE: {residual_qty}")

            if residual_qty > 0:
                # Estrai altri dati dall'item annidato
                item_data = item.get('item', {}) if 'item' in item else item
                
                residual_data = {
                    "sku": sku,
                    "quantity": residual_qty,
                    "name": item_data.get('title') or item_data.get('name'),
                    "asin": item_data.get('asin'),
                    "fnsku": item_data.get('fnsku'),
                    "photo_url": item_data.get('photo_url'),
                }
                residual_items.append(residual_data)
                logger.info(f"  -> ✅ AGGIUNTO: SKU {sku} con quantità residuale {residual_qty}")
        
        logger.info(f"--- Fine Calcolo Residuali: {len(residual_items)} items totali ---")
        return residual_items

    def _send_telegram_notification_if_needed(self, update: ShipmentStatusUpdate, result: Dict[str, Any]):
        notify_events = ['inbound_shipment.created', 'inbound_shipment.received', 'outbound_shipment.created', 'outbound_shipment.closed']
        if update.event_type not in notify_events: return

        try:
            merchant_email = self._get_merchant_email(update.merchant_id)
            if not merchant_email:
                logger.warning(f"Email per merchant {update.merchant_id} non trovata. Notifica saltata.")
                return
            
            # Ottieni il nome del merchant
            merchant_name = self._get_merchant_name(update.merchant_id)
            
            # Estrai i dati dal payload del webhook
            data = update.payload.get('data', {})
            
            # Formatta i dati per la notifica
            shipment_data = {
                'shipment_id': data.get('id', update.shipment_id),
                'shipment_name': data.get('name', ''),
                'merchant_name': merchant_name or 'Cliente',
                'tracking_number': data.get('tracking_number', ''),
                'carrier': data.get('carrier', ''),
                'notes': data.get('notes', ''),
            }
            
            # Aggiungi informazioni sui prodotti se disponibili nel payload
            if update.payload.get('products_summary'):
                # Estrai il numero di prodotti dal summary
                summary = update.payload.get('products_summary', '')
                if 'prodotti' in summary:
                    try:
                        # Estrai il numero dal formato "3 prodotti, 17 unità totali"
                        products_count = int(summary.split(' ')[0])
                        shipment_data['products_count'] = products_count
                    except (ValueError, IndexError):
                        pass
            
            # Per eventi di spedizione in entrata ricevuta, aggiungi conteggi
            if update.event_type == 'inbound_shipment.received':
                shipment_data['expected_count'] = data.get('expected_count')
                shipment_data['received_count'] = data.get('received_count')
            
            message = format_shipment_notification(update.event_type, shipment_data, 'it')
            
            send_telegram_notification(email=merchant_email, message=message, event_type=update.event_type, shipment_id=update.shipment_id)
            logger.info(f"Notifica Telegram per merchant {update.merchant_id} accodata con successo.")
        except Exception as e:
            logger.error(f"Errore durante l'accodamento della notifica Telegram: {e}", exc_info=True)

    def _get_merchant_email(self, merchant_id: str) -> Optional[str]:
        try:
            merchants_resp = self.client.get_merchants()
            if merchants_resp and merchants_resp.data:
                # Cerca il merchant specifico nella lista
                merchant = next((m for m in merchants_resp.data if str(m.id) == str(merchant_id)), None)
                if merchant:
                    return merchant.primaryEmail
        except Exception as e:
            logger.error(f"Impossibile recuperare email per merchant {merchant_id}: {e}")
        return None

    def _get_merchant_name(self, merchant_id: str) -> Optional[str]:
        """Ottiene il nome del merchant dal suo ID."""
        try:
            merchants_resp = self.client.get_merchants()
            if merchants_resp and merchants_resp.data:
                # Cerca il merchant specifico nella lista
                merchant = next((m for m in merchants_resp.data if str(m.id) == str(merchant_id)), None)
                if merchant:
                    return merchant.name
        except Exception as e:
            logger.error(f"Impossibile recuperare nome per merchant {merchant_id}: {e}")
        return None 