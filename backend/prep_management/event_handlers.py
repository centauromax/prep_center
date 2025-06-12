"""
Modulo per l'elaborazione degli eventi webhook specifici dell'applicazione.
Contiene la logica di business per reagire ai vari tipi di eventi.
"""

import logging
import time
import traceback
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
import pytz

from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist

from .models import ShipmentStatusUpdate, OutgoingMessage, TelegramNotification
from .utils.messaging import send_outbound_without_inbound_notification
from .services import send_telegram_notification, format_shipment_notification

# Import libs con gestione errori
try:
    from libs.api_client.prep_business import PrepBusinessClient
    from libs.config import (
        PREP_BUSINESS_API_URL,
        PREP_BUSINESS_API_KEY,
        PREP_BUSINESS_API_TIMEOUT,
    )
    LIBS_IMPORT_SUCCESS = True
except ImportError as e:
    logger = logging.getLogger('prep_management')
    logger.error(f"[event_handlers] Errore import libs: {e}")
    PrepBusinessClient = None
    PREP_BUSINESS_API_URL = None
    PREP_BUSINESS_API_KEY = None
    PREP_BUSINESS_API_TIMEOUT = 30
    LIBS_IMPORT_SUCCESS = False

logger = logging.getLogger('prep_management')

class WebhookEventProcessor:
    """
    Classe per elaborare gli eventi webhook ricevuti da PrepBusiness.
    Implementa la logica di business specifica dell'applicazione.
    """
    
    def __init__(self):
        """Inizializza il processore degli eventi."""
        logger.info("[WebhookEventProcessor.__init__] Inizio inizializzazione.")
        
        # Crea un client PrepBusiness per le chiamate API necessarie
        try:
            logger.info("[WebhookEventProcessor.__init__] Tentativo di istanziare PrepBusinessClient.")
            
            if not LIBS_IMPORT_SUCCESS or PrepBusinessClient is None:
                logger.error("[WebhookEventProcessor.__init__] Import libs fallito, client non disponibile.")
                self.client = None
            else:
                # Uso del client originale con api_url e api_key
                self.client = PrepBusinessClient(
                    api_url=PREP_BUSINESS_API_URL,
                    api_key=PREP_BUSINESS_API_KEY
                )
                logger.info("[WebhookEventProcessor.__init__] PrepBusinessClient istanziato con successo.")
        except Exception as e_client_init:
            logger.error(f"[WebhookEventProcessor.__init__] Eccezione durante l'istanza di PrepBusinessClient: {e_client_init}")
            self.client = None
        
        logger.info("[WebhookEventProcessor.__init__] Fine inizializzazione.")
    
    def process_event(self, update_id: int) -> Dict[str, Any]: 
        """
        Elabora un evento webhook in base al suo tipo.
        
        Args:
            update_id: ID dell'aggiornamento ShipmentStatusUpdate da elaborare
            
        Returns:
            Dizionario con i risultati dell'elaborazione
        """
        logger.info(f"[WebhookEventProcessor.process_event] Inizio elaborazione per update_id: {update_id}")
        try:
            # Recupera l'aggiornamento dal database
            try:
                logger.info(f"[WebhookEventProcessor.process_event] Tentativo recupero Update ID: {update_id} dal DB.")
                update = ShipmentStatusUpdate.objects.get(id=update_id)
                logger.info(f"[WebhookEventProcessor.process_event] Update ID: {update_id} recuperato.")
            except ShipmentStatusUpdate.DoesNotExist:
                logger.warning(f"[WebhookEventProcessor.process_event] Aggiornamento con ID {update_id} non trovato nel DB.")
                return {
                    'success': False,
                    'message': f'Aggiornamento con ID {update_id} non trovato',
                    'error': 'update_not_found'
                }
            
            # Se già elaborato, restituisce il risultato salvato
            if update.processed:
                logger.info(f"[WebhookEventProcessor.process_event] Update ID: {update_id} già processato. Salto.")
                return {
                    'success': True,
                    'message': 'Aggiornamento già elaborato in precedenza',
                    'processed': True,
                    'process_result': update.process_result or {}
                }
            
            # Elabora in base al tipo di evento
            event_type = update.event_type
            logger.info(f"[WebhookEventProcessor.process_event] Evento tipo: {event_type} per Update ID: {update_id}.")
            result = None
            
            if event_type == 'outbound_shipment.created':
                logger.info(f"[WebhookEventProcessor.process_event] Chiamata a _process_outbound_shipment_created per Update ID: {update_id}.")
                result = self._process_outbound_shipment_created(update)
            elif event_type.startswith('inbound_shipment.'):
                logger.info(f"[WebhookEventProcessor.process_event] Chiamata a _process_inbound_shipment_event per Update ID: {update_id}.")
                result = self._process_inbound_shipment_event(update)
            elif event_type == 'outbound_shipment.closed':
                logger.info(f"[WebhookEventProcessor.process_event] Chiamata a _process_outbound_shipment_closed per Update ID: {update_id}.")
                result = self._process_outbound_shipment_closed(update)
            else:
                # Handler generico per eventi non specificamente gestiti
                logger.info(f"[WebhookEventProcessor.process_event] Evento {event_type} non gestito specificamente per Update ID: {update_id}.")
                result = {
                    'success': True,
                    'message': f'Evento {event_type} ricevuto ma nessuna elaborazione specifica richiesta',
                }
            
            # Aggiorna il record con il risultato dell'elaborazione
            logger.info(f"[WebhookEventProcessor.process_event] Tentativo salvataggio risultato per Update ID: {update_id}.")
            update.processed = True
            update.processed_at = timezone.now()
            update.process_success = result.get('success', False)
            update.process_message = result.get('message', '')
            update.process_result = result
            update.save()
            logger.info(f"[WebhookEventProcessor.process_event] Risultato salvato per Update ID: {update_id}.")
            
            # Invia notifica Telegram se l'evento lo richiede
            logger.info(f"[WebhookEventProcessor.process_event] Tentativo invio notifica Telegram per evento {update.event_type}")
            self._send_telegram_notification_if_needed(update)
            
            return result
            
        except Exception as e:
            logger.error(f"[WebhookEventProcessor.process_event] Eccezione durante process_event per Update ID: {update_id}. Errore: {e}")
            logger.exception("Traceback completo:")
            
            # Aggiorna il record con l'errore
            try:
                logger.info(f"[WebhookEventProcessor.process_event] Tentativo salvataggio errore per Update ID: {update_id}.")
                update.processed = True
                update.processed_at = timezone.now()
                update.process_success = False
                update.process_message = f"Errore: {e}"
                update.process_result = {
                    'success': False,
                    'error': 'processing_exception',
                    'message': str(e)
                }
                update.save()
                logger.info(f"[WebhookEventProcessor.process_event] Errore salvato per Update ID: {update_id}.")
            except Exception:
                # In caso di errore anche nel salvataggio, logga e continua
                logger.exception("[WebhookEventProcessor.process_event] Eccezione durante il salvataggio dell'errore di elaborazione.")
            
            return {
                'success': False,
                'message': f'Errore durante l\'elaborazione: {e}',
                'error': 'processing_exception'
            }
    
    def _process_outbound_shipment_created(self, update: ShipmentStatusUpdate) -> Dict[str, Any]:
        """
        Elabora l'evento di creazione di una spedizione in uscita.
        """
        return {
            'success': True,
            'message': 'Evento outbound shipment created elaborato',
        }
    
    def _process_inbound_shipment_event(self, update: ShipmentStatusUpdate) -> Dict[str, Any]:
        """
        Elabora eventi per spedizioni in entrata.
        """
        return {
            'success': True,
            'message': f'Evento inbound shipment {update.event_type} elaborato correttamente',
        }
    
    def _process_outbound_shipment_closed(self, update: ShipmentStatusUpdate) -> Dict[str, Any]:
        """
        Elabora l'evento di chiusura di una spedizione in uscita.
        Implementa la logica per creare inbound residuali automaticamente.
        """
        logger.info(f"[_process_outbound_shipment_closed] 🚀 Inizio elaborazione outbound shipment closed")
        
        try:
            # Estrai i dati dalla payload del webhook
            payload = update.payload or {}
            shipment_data = payload.get('data', {})
            
            if not shipment_data:
                logger.warning(f"[_process_outbound_shipment_closed] ⚠️ Nessun dato shipment nella payload")
                return {
                    'success': False,
                    'message': 'Dati shipment mancanti nella payload webhook',
                }
            
            shipment_id = shipment_data.get('id') or shipment_data.get('shipment_id')
            shipment_name = shipment_data.get('name', '')
            merchant_id = shipment_data.get('merchant_id', '')
            
            if not shipment_id:
                logger.warning(f"[_process_outbound_shipment_closed] ⚠️ Shipment ID mancante")
                return {
                    'success': False,
                    'message': 'Shipment ID mancante nei dati webhook',
                }
            
            logger.info(f"[_process_outbound_shipment_closed] 📦 Processing shipment ID: {shipment_id}, name: '{shipment_name}'")
            
            # 1. Recupera gli items della spedizione outbound appena chiusa
            logger.info(f"[_process_outbound_shipment_closed] 📋 Step 1: Recupero items outbound shipment {shipment_id}")
            outbound_items = self._get_outbound_shipment_items(str(shipment_id))
            
            if not outbound_items:
                logger.warning(f"[_process_outbound_shipment_closed] ⚠️ Nessun item trovato nell'outbound shipment {shipment_id}")
                return {
                    'success': True,
                    'message': f'Outbound shipment {shipment_id} chiuso ma nessun item trovato - nessun residual necessario',
                }
            
            logger.info(f"[_process_outbound_shipment_closed] ✅ Trovati {len(outbound_items)} items nell'outbound")
            
            # 2. Trova l'inbound shipment corrispondente (stesso nome)
            logger.info(f"[_process_outbound_shipment_closed] 🔍 Step 2: Ricerca inbound shipment con nome '{shipment_name}'")
            inbound_shipment = self._find_matching_inbound_shipment(shipment_name, merchant_id)
            
            if not inbound_shipment:
                logger.warning(f"[_process_outbound_shipment_closed] ⚠️ Nessun inbound shipment trovato con nome '{shipment_name}'")
                return {
                    'success': True,
                    'message': f'Nessun inbound shipment trovato con nome "{shipment_name}" - nessun residual necessario',
                }
            
            inbound_id = inbound_shipment.get('id')
            warehouse_id = inbound_shipment.get('warehouse_id')
            logger.info(f"[_process_outbound_shipment_closed] ✅ Trovato inbound shipment ID: {inbound_id}")
            
            # 3. Recupera gli items dell'inbound shipment
            logger.info(f"[_process_outbound_shipment_closed] 📋 Step 3: Recupero items inbound shipment {inbound_id}")
            inbound_items = self._get_inbound_shipment_items(str(inbound_id))
            
            if not inbound_items:
                logger.warning(f"[_process_outbound_shipment_closed] ⚠️ Nessun item trovato nell'inbound shipment {inbound_id}")
                return {
                    'success': True,
                    'message': f'Inbound shipment {inbound_id} trovato ma nessun item - nessun residual necessario',
                }
            
            logger.info(f"[_process_outbound_shipment_closed] ✅ Trovati {len(inbound_items)} items nell'inbound")
            
            # 4. Calcola i prodotti residuali
            logger.info(f"[_process_outbound_shipment_closed] 🧮 Step 4: Calcolo prodotti residuali")
            residual_items = self._calculate_residual_items(inbound_items, outbound_items)
            
            if not residual_items:
                logger.info(f"[_process_outbound_shipment_closed] ✅ Nessun prodotto residuale calcolato - tutto spedito")
                return {
                    'success': True,
                    'message': 'Tutti i prodotti sono stati spediti - nessun residual necessario',
                }
            
            logger.info(f"[_process_outbound_shipment_closed] ✅ Calcolati {len(residual_items)} prodotti residuali")
            
            # 5. Genera nome per il nuovo inbound residual
            logger.info(f"[_process_outbound_shipment_closed] 🏷️ Step 5: Generazione nome per inbound residual")
            residual_name = self._generate_residual_name(shipment_name, merchant_id)
            logger.info(f"[_process_outbound_shipment_closed] ✅ Nome generato: '{residual_name}'")
            
            # 6. Crea il nuovo inbound shipment residual
            logger.info(f"[_process_outbound_shipment_closed] 🚀 Step 6: Creazione inbound residual")
            residual_id = self._create_residual_inbound_shipment(
                name=residual_name,
                warehouse_id=warehouse_id,
                items=residual_items,
                merchant_id=merchant_id
            )
            
            if residual_id:
                logger.info(f"[_process_outbound_shipment_closed] 🎉 SUCCESS: Inbound residual creato con ID: {residual_id}")
                return {
                    'success': True,
                    'message': f'Inbound residual creato con successo - ID: {residual_id}, Nome: "{residual_name}"',
                    'residual_inbound_id': residual_id,
                    'residual_name': residual_name,
                    'residual_items_count': len(residual_items)
                }
            else:
                logger.error(f"[_process_outbound_shipment_closed] ❌ ERRORE: Creazione inbound residual fallita")
                return {
                    'success': False,
                    'message': 'Errore durante la creazione dell\'inbound residual',
                }
                
        except Exception as e:
            logger.error(f"[_process_outbound_shipment_closed] ❌ ECCEZIONE: {str(e)}")
            logger.exception("Traceback completo:")
            return {
                'success': False,
                'message': f'Errore durante l\'elaborazione outbound shipment closed: {str(e)}',
                'error': 'processing_exception'
            }
    
    def _send_telegram_notification_if_needed(self, update: ShipmentStatusUpdate):
        """
        Invia una notifica Telegram se l'evento lo richiede.
        """
        # Lista degli eventi per cui inviare notifiche
        notify_events = [
            'inbound_shipment.created',    
            'inbound_shipment.received',
            'inbound_shipment.shipped', 
            'outbound_shipment.created',
            'outbound_shipment.closed',
            'order.created',
            'order.shipped'
        ]
        
        # Controlla se l'evento richiede una notifica
        if update.event_type not in notify_events:
            logger.info(f"[_send_telegram_notification_if_needed] Evento {update.event_type} non richiede notifica.")
            return
        
        logger.info(f"[_send_telegram_notification_if_needed] Invio notifica per evento {update.event_type}")
        
        try:
            # Recupera l'email del merchant
            merchant_email = self._get_merchant_email(update.merchant_id)
            if not merchant_email:
                logger.warning(f"[_send_telegram_notification_if_needed] Nessuna email trovata per merchant {update.merchant_id}")
                return
            
            logger.info(f"[_send_telegram_notification_if_needed] Email merchant trovata: {merchant_email}")
            
            # Estrai i dati della spedizione dal payload del webhook
            shipment_data = {}
            if update.payload and 'data' in update.payload:
                raw_data = update.payload['data']
                
                # Mappa i dati con i nomi di campo corretti per il formattatore
                shipment_data = {
                    'shipment_id': update.shipment_id,
                    'shipment_name': raw_data.get('name'),  # Mappa 'name' a 'shipment_name'
                    'tracking_number': raw_data.get('tracking_number'),
                    'carrier': raw_data.get('carrier'),
                    'notes': raw_data.get('notes'),
                    'products_count': raw_data.get('products_count'),
                    'expected_count': raw_data.get('expected_count'),
                    'received_count': raw_data.get('received_count')
                }
                
                logger.info(f"[_send_telegram_notification_if_needed] Dati spedizione mappati: {shipment_data}")
            else:
                # Se non ci sono dati nel payload, almeno passa l'ID
                shipment_data = {
                    'shipment_id': update.shipment_id
                }
                logger.warning(f"[_send_telegram_notification_if_needed] Nessun dato spedizione nel payload, usando solo shipment_id")
            
            # Invia la notifica (la formattazione del messaggio sarà gestita internamente)
            success = send_telegram_notification(
                email=merchant_email,
                message=None,  # Verrà formattato internamente
                event_type=update.event_type,
                shipment_id=update.shipment_id,
                shipment_data=shipment_data  # Passiamo i dati per la formattazione
            )
            
            if success:
                logger.info(f"[_send_telegram_notification_if_needed] ✅ Notifica Telegram inviata per evento {update.event_type} a {merchant_email}")
            else:
                logger.warning(f"[_send_telegram_notification_if_needed] ❌ Notifica Telegram fallita per evento {update.event_type} a {merchant_email}")
                
        except Exception as e:
            logger.error(f"[_send_telegram_notification_if_needed] Errore nell'invio notifica Telegram: {e}")
            logger.exception("Traceback completo:")
    
    def _get_merchant_email(self, merchant_id: str) -> Optional[str]:
        """
        Recupera l'email del merchant tramite API.
        
        Args:
            merchant_id: ID del merchant
            
        Returns:
            Email del merchant o None se non trovata
        """
        logger.info(f"[_get_merchant_email] Recupero email per merchant {merchant_id}")
        
        try:
            if self.client is None:
                logger.error("[_get_merchant_email] Client API non disponibile!")
                return None
            
            # Ottieni tutti i merchants
            merchants = self.client.get_merchants()
            logger.info(f"[_get_merchant_email] Recuperati {len(merchants)} merchants")
            
            # Trova il merchant con l'ID specificato
            merchant = next((m for m in merchants if str(m.get('id', '')) == str(merchant_id)), None)
            
            if merchant:
                # Prova prima primaryEmail, poi email per retrocompatibilità
                email = merchant.get('primaryEmail') or merchant.get('email')
                if email:
                    logger.info(f"[_get_merchant_email] ✅ Email trovata per merchant {merchant_id}: {email}")
                    return email
                else:
                    logger.warning(f"[_get_merchant_email] ❌ Merchant {merchant_id} trovato ma SENZA primaryEmail/email")
                    return None
            else:
                logger.warning(f"[_get_merchant_email] ❌ Merchant {merchant_id} NON trovato nella lista")
                return None
                
        except Exception as e:
            logger.error(f"[_get_merchant_email] Errore durante il recupero email per merchant {merchant_id}: {e}")
            logger.exception("Traceback completo:")
            return None

    def _get_outbound_shipment_items(self, shipment_id: str) -> List[Dict[str, Any]]:
        """
        Recupera tutti gli items di un outbound shipment.
        
        Args:
            shipment_id: ID della spedizione
            
        Returns:
            Lista di dict con i dettagli degli items
        """
        logger.info(f"[_get_outbound_shipment_items] 🚀 Recupero items outbound shipment_id={shipment_id}")
        
        if self.client is None:
            logger.error("[_get_outbound_shipment_items] ❌ Client API non disponibile!")
            return []
        
        try:
            items_response = self.client.get_outbound_shipment_items(shipment_id=int(shipment_id))
            
            if items_response and isinstance(items_response, list):
                items = []
                for item in items_response:
                    # Il client wrapper restituisce dict
                    item_data = {
                        'item_id': item.get('item_id') or item.get('id'),
                        'merchant_sku': item.get('merchant_sku', ''),
                        'title': item.get('title', ''),
                        'asin': item.get('asin', ''),
                        'fnsku': item.get('fnsku', ''),
                        'quantity': item.get('quantity', 0)
                    }
                    items.append(item_data)
                    logger.debug(f"[_get_outbound_shipment_items] 📦 Item: {item_data}")
                
                logger.info(f"[_get_outbound_shipment_items] ✅ Recuperati {len(items)} items")
                return items
            else:
                logger.warning(f"[_get_outbound_shipment_items] ⚠️ Nessun item trovato nella risposta API")
                return []
                
        except Exception as e:
            logger.error(f"[_get_outbound_shipment_items] ❌ Errore recupero items: {str(e)}")
            logger.exception("Traceback:")
            return []

    def _get_inbound_shipment_items(self, shipment_id: str) -> List[Dict[str, Any]]:
        """
        Recupera tutti gli items di un inbound shipment.
        
        Args:
            shipment_id: ID della spedizione
            
        Returns:
            Lista di dict con i dettagli degli items (expected/actual quantities)
        """
        logger.info(f"[_get_inbound_shipment_items] 🚀 Recupero items inbound shipment_id={shipment_id}")
        
        if self.client is None:
            logger.error("[_get_inbound_shipment_items] ❌ Client API non disponibile!")
            return []
        
        try:
            items_response = self.client.get_inbound_shipment_items(shipment_id=int(shipment_id))
            
            # 🔍 DEBUG: Logga la risposta completa dell'API
            logger.info(f"[_get_inbound_shipment_items] 🔍 DEBUG API Response type: {type(items_response)}")
            logger.debug(f"[_get_inbound_shipment_items] 🔍 DEBUG API Response content: {items_response}")
            
            if items_response and isinstance(items_response, list):
                logger.info(f"[_get_inbound_shipment_items] ✅ API restituisce lista con {len(items_response)} elements")
                
                items = []
                for i, item in enumerate(items_response):
                    logger.debug(f"[_get_inbound_shipment_items] 🔍 Raw item {i}: {item}")
                    
                    # Il client wrapper restituisce dict
                    item_data = {
                        'item_id': item.get('item_id') or item.get('id'),
                        'merchant_sku': item.get('merchant_sku', ''),
                        'title': item.get('title', ''),
                        'asin': item.get('asin', ''),
                        'fnsku': item.get('fnsku', ''),
                        'expected_quantity': item.get('expected_quantity', 0),
                        'actual_quantity': item.get('actual_quantity', 0)
                    }
                    items.append(item_data)
                    logger.debug(f"[_get_inbound_shipment_items] 📦 Converted item {i}: {item_data}")
                
                logger.info(f"[_get_inbound_shipment_items] ✅ Recuperati {len(items)} items")
                return items
            else:
                logger.warning(f"[_get_inbound_shipment_items] ⚠️ Risposta API vuota o non lista: {items_response}")
                return []
                
        except Exception as e:
            logger.error(f"[_get_inbound_shipment_items] ❌ Errore recupero items: {str(e)}")
            logger.exception("Traceback:")
            return []
    
    def _calculate_residual_items(self, inbound_items: List[Dict[str, Any]], outbound_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Calcola i prodotti residuali sottraendo le quantità spedite dall'inbound originale.
        
        Args:
            inbound_items: Lista items dell'inbound originale
            outbound_items: Lista items dell'outbound completato
            
        Returns:
            Lista di dict con i prodotti residuali (con quantità > 0)
        """
        logger.info(f"[_calculate_residual_items] 🧮 Calcolo residual da {len(inbound_items)} inbound e {len(outbound_items)} outbound items")
        
        # Crea un mapping dei prodotti outbound per item_id
        outbound_quantities = {}
        for item in outbound_items:
            item_id = item.get('item_id')
            quantity_shipped = item.get('quantity', 0)
            outbound_quantities[item_id] = outbound_quantities.get(item_id, 0) + quantity_shipped
            logger.debug(f"[_calculate_residual_items] 📤 Outbound - Item ID {item_id}: {quantity_shipped} shipped")
        
        residual_items = []
        
        for inbound_item in inbound_items:
            item_id = inbound_item.get('item_id')
            expected_qty = inbound_item.get('expected_quantity', 0)
            actual_qty = inbound_item.get('actual_quantity', 0)
            shipped_qty = outbound_quantities.get(item_id, 0)
            
            # Calcola le quantità residuali
            residual_expected = max(0, expected_qty - shipped_qty)
            residual_actual = max(0, actual_qty - shipped_qty)
            
            logger.debug(f"[_calculate_residual_items] 📊 Item ID {item_id}: Expected {expected_qty} - Shipped {shipped_qty} = Residual Expected {residual_expected}")
            logger.debug(f"[_calculate_residual_items] 📊 Item ID {item_id}: Actual {actual_qty} - Shipped {shipped_qty} = Residual Actual {residual_actual}")
            
            # Includi solo se almeno una delle quantità è > 0
            if residual_expected > 0 or residual_actual > 0:
                residual_item = {
                    'item_id': item_id,
                    'merchant_sku': inbound_item.get('merchant_sku', ''),
                    'title': inbound_item.get('title', ''),
                    'asin': inbound_item.get('asin', ''),
                    'fnsku': inbound_item.get('fnsku', ''),
                    'expected_quantity': residual_expected,
                    'actual_quantity': residual_actual
                }
                residual_items.append(residual_item)
                logger.debug(f"[_calculate_residual_items] ✅ Aggiunto residual: {residual_item}")
            else:
                logger.debug(f"[_calculate_residual_items] ❌ Item ID {item_id} - nessun residual (entrambe le quantità = 0)")
        
        logger.info(f"[_calculate_residual_items] ✅ Calcolati {len(residual_items)} prodotti residuali")
        return residual_items
    
    def _find_matching_inbound_shipment(self, shipment_name: str, merchant_id: str) -> Optional[Dict[str, Any]]:
        """
        Trova un inbound shipment con il nome specificato.
        
        Args:
            shipment_name: Nome della spedizione da cercare
            merchant_id: ID del merchant
            
        Returns:
            Dict con i dati dell'inbound shipment o None se non trovato
        """
        logger.info(f"[_find_matching_inbound_shipment] 🔍 Ricerca inbound con nome '{shipment_name}' per merchant {merchant_id}")
        
        if self.client is None:
            logger.error("[_find_matching_inbound_shipment] ❌ Client API non disponibile!")
            return None
        
        try:
            # Cerca tra tutti gli inbound shipments del merchant
            shipments = self.client.get_shipments(merchant_id=int(merchant_id))
            
            if not shipments:
                logger.warning(f"[_find_matching_inbound_shipment] ⚠️ Nessun shipment trovato per merchant {merchant_id}")
                return None
            
            logger.info(f"[_find_matching_inbound_shipment] 📋 Cercando tra {len(shipments)} shipments")
            
            for shipment in shipments:
                shipment_type = shipment.get('type', '').lower()
                current_name = shipment.get('name', '')
                
                # Filtra solo gli inbound shipments
                if shipment_type == 'inbound' and current_name == shipment_name:
                    logger.info(f"[_find_matching_inbound_shipment] ✅ Trovato inbound shipment: ID {shipment.get('id')}, nome '{current_name}'")
                    return shipment
            
            logger.warning(f"[_find_matching_inbound_shipment] ❌ Nessun inbound shipment trovato con nome '{shipment_name}'")
            return None
                
        except Exception as e:
            logger.error(f"[_find_matching_inbound_shipment] ❌ Errore ricerca inbound shipment: {str(e)}")
            logger.exception("Traceback:")
            return None
    
    def _generate_residual_name(self, original_name: str, merchant_id: str) -> str:
        """
        Genera il nome per l'inbound residual, gestendo numerazione progressiva.
        
        Args:
            original_name: Nome dell'inbound originale
            merchant_id: ID del merchant
            
        Returns:
            Nome generato per il residual (es. "Original - Residual", "Original - Residual 2", ecc.)
        """
        logger.info(f"[_generate_residual_name] 🏷️ Generazione nome residual per '{original_name}'")
        
        base_name = f"{original_name} - Residual"
        
        try:
            # Controlla se esiste già un inbound con questo nome
            if not self._find_matching_inbound_shipment(base_name, merchant_id):
                logger.info(f"[_generate_residual_name] ✅ Nome disponibile: '{base_name}'")
                return base_name
            
            # Se esiste, prova con numerazione progressiva
            counter = 2
            max_attempts = 20  # Limite di sicurezza
            
            while counter <= max_attempts:
                numbered_name = f"{original_name} - Residual {counter}"
                if not self._find_matching_inbound_shipment(numbered_name, merchant_id):
                    logger.info(f"[_generate_residual_name] ✅ Nome disponibile: '{numbered_name}'")
                    return numbered_name
                counter += 1
            
            # Se tutti i nomi sono occupati, aggiungi timestamp
            import time
            timestamp = int(time.time())
            fallback_name = f"{original_name} - Residual {timestamp}"
            logger.warning(f"[_generate_residual_name] ⚠️ Usando nome fallback con timestamp: '{fallback_name}'")
            return fallback_name
            
        except Exception as e:
            logger.error(f"[_generate_residual_name] ❌ Errore generazione nome: {str(e)}")
            # Fallback con timestamp in caso di errore
            import time
            timestamp = int(time.time())
            fallback_name = f"{original_name} - Residual {timestamp}"
            logger.warning(f"[_generate_residual_name] ⚠️ Usando nome fallback per errore: '{fallback_name}'")
            return fallback_name
    
    def _create_residual_inbound_shipment(self, name: str, warehouse_id: int, items: List[Dict[str, Any]], merchant_id: str) -> Optional[int]:
        """
        Crea un nuovo inbound shipment residual con i prodotti specificati.
        
        Args:
            name: Nome per il nuovo inbound
            warehouse_id: ID del warehouse
            items: Lista di prodotti da aggiungere
            merchant_id: ID del merchant
            
        Returns:
            ID del nuovo inbound shipment o None se errore
        """
        logger.info(f"[_create_residual_inbound_shipment] 🚀 Creazione inbound residual '{name}' con {len(items)} items")
        
        if self.client is None:
            logger.error("[_create_residual_inbound_shipment] ❌ Client API non disponibile!")
            return None
        
        try:
            # Prepara i dati per la creazione dell'inbound shipment
            shipment_data = {
                'name': name,
                'merchant_id': int(merchant_id),
                'warehouse_id': warehouse_id,
                'type': 'inbound',
                'status': 'created'
            }
            
            logger.info(f"[_create_residual_inbound_shipment] 📋 Dati shipment: {shipment_data}")
            
            # Crea l'inbound shipment
            new_shipment = self.client.create_inbound_shipment(shipment_data)
            
            if not new_shipment or not new_shipment.get('id'):
                logger.error(f"[_create_residual_inbound_shipment] ❌ Creazione shipment fallita: {new_shipment}")
                return None
            
            shipment_id = new_shipment.get('id')
            logger.info(f"[_create_residual_inbound_shipment] ✅ Inbound shipment creato con ID: {shipment_id}")
            
            # Aggiungi gli items al shipment
            items_added = 0
            for item in items:
                try:
                    # Prepara i dati dell'item
                    item_data = {
                        'merchant_sku': item.get('merchant_sku', ''),
                        'title': item.get('title', ''),
                        'asin': item.get('asin', ''),
                        'fnsku': item.get('fnsku', ''),
                        'expected_quantity': item.get('expected_quantity', 0),
                        'actual_quantity': item.get('actual_quantity', 0)
                    }
                    
                    logger.debug(f"[_create_residual_inbound_shipment] 📦 Aggiunta item: {item_data}")
                    
                    # Aggiungi l'item al shipment (ora disponibile dopo la migrazione!)
                    result = self.client.add_item_to_shipment(shipment_id, item_data)
                    
                    if result:
                        items_added += 1
                        logger.debug(f"[_create_residual_inbound_shipment] ✅ Item aggiunto: {item.get('merchant_sku', 'N/A')}")
                    else:
                        logger.warning(f"[_create_residual_inbound_shipment] ⚠️ Aggiunta item fallita: {item.get('merchant_sku', 'N/A')}")
                        
                except Exception as e_item:
                    logger.error(f"[_create_residual_inbound_shipment] ❌ Errore aggiunta item {item.get('merchant_sku', 'N/A')}: {str(e_item)}")
                    continue
            
            logger.info(f"[_create_residual_inbound_shipment] ✅ Aggiunti {items_added}/{len(items)} items al shipment {shipment_id}")
            
            if items_added > 0:
                logger.info(f"[_create_residual_inbound_shipment] 🎉 SUCCESS: Inbound residual creato completamente - ID: {shipment_id}")
                return shipment_id
            else:
                logger.error(f"[_create_residual_inbound_shipment] ❌ Nessun item aggiunto - eliminazione shipment vuoto")
                # Potresti voler eliminare il shipment vuoto qui, ma per sicurezza lo lasciamo
                return None
                
        except Exception as e:
            logger.error(f"[_create_residual_inbound_shipment] ❌ Errore creazione inbound residual: {str(e)}")
            logger.exception("Traceback:")
            return None 