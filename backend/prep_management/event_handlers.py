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
from django.conf import settings

from .models import ShipmentStatusUpdate, OutgoingMessage, TelegramNotification
from .utils.messaging import send_outbound_without_inbound_notification
from .services import send_telegram_notification, format_shipment_notification

# Import libs con gestione errori
try:
    from libs.prepbusiness.client import PrepBusinessClient
    from libs.prepbusiness.models import Carrier
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
    Carrier = None
    PREP_BUSINESS_API_URL = None
    PREP_BUSINESS_API_KEY = None
    PREP_BUSINESS_API_TIMEOUT = 30
    LIBS_IMPORT_SUCCESS = False

logger = logging.getLogger('prep_management')

# HOTFIX: Mapping hardcodato dei merchant emails per garantire le notifiche Telegram
MERCHANT_EMAIL_FALLBACK = {
    "7812": "prep@easyavant.com",
    "8185": "commerciale@selley.it",
    # Aggiungi altri se necessario
}

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
                # HOTFIX: Prova prima l'inizializzazione standard del client completo
                try:
                    self.client = PrepBusinessClient(
                        api_key=settings.PREP_BUSINESS_API_KEY,
                        company_domain="dashboard.fbaprepcenteritaly.com",
                        timeout=30
                    )
                    logger.info("[WebhookEventProcessor.__init__] ✅ PrepBusinessClient completo istanziato con successo.")
                except Exception as e_complete:
                    logger.error(f"[WebhookEventProcessor.__init__] ❌ Errore client completo: {e_complete}")
                    
                    # FALLBACK: Prova con il wrapper che funziona per le notifiche
                    try:
                        from libs.api_client.prep_business import PrepBusinessClient as WrapperClient
                        self.client = WrapperClient()
                        logger.info("[WebhookEventProcessor.__init__] ✅ FALLBACK: Client wrapper istanziato con successo.")
                    except Exception as e_wrapper:
                        logger.error(f"[WebhookEventProcessor.__init__] ❌ Errore anche con wrapper: {e_wrapper}")
                        self.client = None
                        
        except Exception as e_client_init:
            logger.error(f"[WebhookEventProcessor.__init__] Eccezione durante l'istanza di PrepBusinessClient: {e_client_init}")
            logger.exception("Traceback completo:")
            self.client = None
        
        # Log finale dello stato del client
        if self.client is not None:
            logger.info("[WebhookEventProcessor.__init__] ✅ Client inizializzato correttamente.")
        else:
            logger.error("[WebhookEventProcessor.__init__] ❌ ERRORE: Client NON inizializzato!")
            
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
            
            # HOTFIX: Gestisci sia il formato reale (payload.data) che quello di test (payload root)
            shipment_data = payload.get('data', {})
            if not shipment_data:
                # Se non c'è 'data', prova a usare il payload root (formato test)
                shipment_data = payload
                logger.info(f"[_process_outbound_shipment_closed] 🔧 Usando payload root come shipment_data (formato test)")
            else:
                logger.info(f"[_process_outbound_shipment_closed] 🔧 Usando payload.data come shipment_data (formato reale)")
            
            if not shipment_data:
                logger.warning(f"[_process_outbound_shipment_closed] ⚠️ Nessun dato shipment nella payload")
                logger.warning(f"[_process_outbound_shipment_closed] 🔍 Payload keys: {list(payload.keys())}")
                return {
                    'success': False,
                    'message': 'Dati shipment mancanti nella payload webhook',
                }
            
            shipment_id = shipment_data.get('id') or shipment_data.get('shipment_id')
            shipment_name = shipment_data.get('name', '')
            
            # Prova diversi modi per ottenere merchant_id dal payload
            merchant_id = (
                shipment_data.get('merchant_id') or
                shipment_data.get('merchantId') or  
                shipment_data.get('client_id') or
                shipment_data.get('team_id') or  # AGGIUNTO: team_id per formato test
                update.merchant_id or  # Fallback dal modello update
                ''
            )
            
            # Validazione merchant_id
            if not merchant_id or merchant_id == '':
                logger.warning(f"[_process_outbound_shipment_closed] ⚠️ Merchant ID mancante o vuoto nei dati webhook")
                logger.warning(f"[_process_outbound_shipment_closed] 🔍 Payload shipment_data keys: {list(shipment_data.keys())}")
                logger.warning(f"[_process_outbound_shipment_closed] 🔍 Update merchant_id: {update.merchant_id}")
                return {
                    'success': False,
                    'message': 'Merchant ID mancante nei dati webhook - impossibile procedere con inbound residual',
                }
            
            if not shipment_id:
                logger.warning(f"[_process_outbound_shipment_closed] ⚠️ Shipment ID mancante")
                return {
                    'success': False,
                    'message': 'Shipment ID mancante nei dati webhook',
                }
            
            logger.info(f"[_process_outbound_shipment_closed] 📦 Processing shipment ID: {shipment_id}, name: '{shipment_name}', merchant: {merchant_id}")
            
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
            inbound_shipment = self._find_matching_inbound_shipment(shipment_name, str(merchant_id))
            
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
            residual_name = self._generate_residual_name(shipment_name, str(merchant_id))
            logger.info(f"[_process_outbound_shipment_closed] ✅ Nome generato: '{residual_name}'")
            
            # 6. Crea il nuovo inbound shipment residual
            logger.info(f"[_process_outbound_shipment_closed] 🚀 Step 6: Creazione inbound residual")
            residual_id = self._create_residual_inbound_shipment(residual_name, inbound_shipment, residual_items)
            
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
        
        # HOTFIX: Prima prova il fallback hardcodato per garantire le notifiche
        if str(merchant_id) in MERCHANT_EMAIL_FALLBACK:
            fallback_email = MERCHANT_EMAIL_FALLBACK[str(merchant_id)]
            logger.info(f"[_get_merchant_email] ✅ FALLBACK: Email per merchant {merchant_id}: {fallback_email}")
            
            # Se il client non è disponibile, usa direttamente il fallback
            if self.client is None:
                logger.warning("[_get_merchant_email] Client API non disponibile, uso fallback")
                return fallback_email
        
        try:
            if self.client is None:
                logger.error("[_get_merchant_email] Client API non disponibile!")
                # Se abbiamo un fallback, usalo, altrimenti None
                if str(merchant_id) in MERCHANT_EMAIL_FALLBACK:
                    return MERCHANT_EMAIL_FALLBACK[str(merchant_id)]
                return None
            
            # Ottieni tutti i merchants - il client completo restituisce MerchantsResponse
            merchants_response = self.client.get_merchants()
            
            # Estrai la lista di merchants dal response object
            if hasattr(merchants_response, 'data'):
                merchants_list = [m.model_dump() for m in merchants_response.data]
            elif hasattr(merchants_response, 'merchants'):
                merchants_list = [m.model_dump() for m in merchants_response.merchants]
            else:
                # Fallback se è già una lista (non dovrebbe succedere con client completo)
                merchants_list = merchants_response if isinstance(merchants_response, list) else []
            
            logger.info(f"[_get_merchant_email] Recuperati {len(merchants_list)} merchants")
            
            # Trova il merchant con l'ID specificato
            merchant = next((m for m in merchants_list if str(m.get('id', '')) == str(merchant_id)), None)
            
            if merchant:
                # Prova prima primaryEmail, poi email per retrocompatibilità
                email = merchant.get('primaryEmail') or merchant.get('email')
                if email:
                    logger.info(f"[_get_merchant_email] ✅ Email trovata per merchant {merchant_id}: {email}")
                    return email
                else:
                    logger.warning(f"[_get_merchant_email] ❌ Merchant {merchant_id} trovato ma SENZA primaryEmail/email")
                    # Se abbiamo un fallback, usalo
                    if str(merchant_id) in MERCHANT_EMAIL_FALLBACK:
                        logger.info(f"[_get_merchant_email] 🔄 Uso fallback per merchant {merchant_id}")
                        return MERCHANT_EMAIL_FALLBACK[str(merchant_id)]
                    return None
            else:
                logger.warning(f"[_get_merchant_email] ❌ Merchant {merchant_id} NON trovato nella lista")
                # Se abbiamo un fallback, usalo
                if str(merchant_id) in MERCHANT_EMAIL_FALLBACK:
                    logger.info(f"[_get_merchant_email] 🔄 Uso fallback per merchant {merchant_id}")
                    return MERCHANT_EMAIL_FALLBACK[str(merchant_id)]
                return None
                
        except Exception as e:
            logger.error(f"[_get_merchant_email] Errore durante il recupero email per merchant {merchant_id}: {e}")
            logger.exception("Traceback completo:")
            # In caso di errore, usa il fallback se disponibile
            if str(merchant_id) in MERCHANT_EMAIL_FALLBACK:
                logger.info(f"[_get_merchant_email] 🔄 Errore API, uso fallback per merchant {merchant_id}")
                return MERCHANT_EMAIL_FALLBACK[str(merchant_id)]
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
            
            # Il client completo restituisce OutboundShipmentItemsResponse
            if hasattr(items_response, 'items'):
                items_list = [item.model_dump() for item in items_response.items]
            elif hasattr(items_response, 'data'):
                items_list = items_response.data
            else:
                items_list = items_response if isinstance(items_response, list) else []
            
            if items_list:
                items = []
                for item in items_list:
                    # Il client completo restituisce dict strutturati
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
            
            # Il client completo restituisce ShipmentItemsResponse
            if hasattr(items_response, 'items'):
                items_list = [item.model_dump() for item in items_response.items]
                logger.info(f"[_get_inbound_shipment_items] ✅ API restituisce response.items con {len(items_list)} elements")
            elif hasattr(items_response, 'data'):
                items_list = items_response.data
                logger.info(f"[_get_inbound_shipment_items] ✅ API restituisce response.data con {len(items_list)} elements")
            else:
                items_list = items_response if isinstance(items_response, list) else []
                logger.info(f"[_get_inbound_shipment_items] ✅ API restituisce lista diretta con {len(items_list)} elements")
            
            if items_list:
                items = []
                for i, item in enumerate(items_list):
                    logger.debug(f"[_get_inbound_shipment_items] 🔍 Raw item {i}: {item}")
                    
                    # Il client completo restituisce dict strutturati con nested objects
                    # Estrai le quantità dalle strutture annidate
                    expected_data = item.get('expected', {})
                    actual_data = item.get('actual', {})
                    item_info = item.get('item', {})
                    
                    expected_quantity = expected_data.get('quantity', 0) if isinstance(expected_data, dict) else 0
                    actual_quantity = actual_data.get('quantity', 0) if isinstance(actual_data, dict) else 0
                    
                    # Estrai i dati dell'item dal nested object
                    merchant_sku = item_info.get('merchant_sku', '') if isinstance(item_info, dict) else item.get('merchant_sku', '')
                    title = item_info.get('title', '') if isinstance(item_info, dict) else item.get('title', '')
                    asin = item_info.get('asin', '') if isinstance(item_info, dict) else item.get('asin', '')
                    fnsku = item_info.get('fnsku', '') if isinstance(item_info, dict) else item.get('fnsku', '')
                    
                    item_data = {
                        'item_id': item.get('item_id') or item.get('id'),
                        'merchant_sku': merchant_sku,
                        'title': title,
                        'asin': asin,
                        'fnsku': fnsku,
                        'expected_quantity': expected_quantity,
                        'actual_quantity': actual_quantity
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
        
        # Validazione merchant_id
        if not merchant_id or merchant_id.strip() == '':
            logger.error("[_find_matching_inbound_shipment] ❌ Merchant ID vuoto o non valido!")
            return None
        
        try:
            # Converti merchant_id a int per l'API
            merchant_id_int = int(merchant_id)
        except (ValueError, TypeError):
            logger.error(f"[_find_matching_inbound_shipment] ❌ Merchant ID non valido per conversione int: '{merchant_id}'")
            return None
        
        try:
            # Cerca tra tutti gli inbound shipments del merchant
            shipments_response = self.client.get_inbound_shipments(merchant_id=merchant_id_int)
            
            # Il client completo restituisce un response object, estrai la lista
            if hasattr(shipments_response, 'shipments'):
                # Gli oggetti shipments sono Pydantic objects, non dict
                shipments = shipments_response.shipments
                logger.info(f"[_find_matching_inbound_shipment] 📋 Cercando tra {len(shipments)} inbound shipments")
                
                for shipment in shipments:
                    # Accesso diretto agli attributi Pydantic, non .get()
                    current_name = getattr(shipment, 'name', '') or ''
                    shipment_id = getattr(shipment, 'id', None)
                    
                    # Non c'è bisogno di filtrare per tipo perché get_inbound_shipments restituisce solo inbound
                    if current_name == shipment_name:
                        logger.info(f"[_find_matching_inbound_shipment] ✅ Trovato inbound shipment: ID {shipment_id}, nome '{current_name}'")
                        # Converte in dict per compatibilità
                        return shipment.model_dump()
                
            elif hasattr(shipments_response, 'data'):
                shipments_list = shipments_response.data
                logger.info(f"[_find_matching_inbound_shipment] 📋 Cercando tra {len(shipments_list)} inbound shipments")
                
                for shipment in shipments_list:
                    if hasattr(shipment, 'model_dump'):
                        # Oggetto Pydantic
                        current_name = getattr(shipment, 'name', '') or ''
                        if current_name == shipment_name:
                            logger.info(f"[_find_matching_inbound_shipment] ✅ Trovato inbound shipment: ID {getattr(shipment, 'id', None)}, nome '{current_name}'")
                            return shipment.model_dump()
                    else:
                        # Dict normale
                        current_name = shipment.get('name', '')
                        if current_name == shipment_name:
                            logger.info(f"[_find_matching_inbound_shipment] ✅ Trovato inbound shipment: ID {shipment.get('id')}, nome '{current_name}'")
                            return shipment
            else:
                # Fallback se è già una lista
                shipments = shipments_response if isinstance(shipments_response, list) else []
                logger.info(f"[_find_matching_inbound_shipment] 📋 Cercando tra {len(shipments)} inbound shipments (fallback)")
                
                for shipment in shipments:
                    if hasattr(shipment, 'model_dump'):
                        # Oggetto Pydantic
                        current_name = getattr(shipment, 'name', '') or ''
                        if current_name == shipment_name:
                            logger.info(f"[_find_matching_inbound_shipment] ✅ Trovato inbound shipment: ID {getattr(shipment, 'id', None)}, nome '{current_name}'")
                            return shipment.model_dump()
                    else:
                        # Dict normale
                        current_name = shipment.get('name', '')
                        if current_name == shipment_name:
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
        
        # ✅ FIX: Gestisci nomi che sono già residual per evitare "test2 - residual - residual"
        base_name_for_residual = original_name
        
        # Se il nome contiene già "- Residual", estrai il nome base originale
        if " - Residual" in original_name:
            # Esempio: "test2 - Residual" -> "test2", "test2 - Residual 3" -> "test2"
            base_name_for_residual = original_name.split(" - Residual")[0]
            logger.info(f"[_generate_residual_name] 🔄 Nome già residual, estratto nome base: '{base_name_for_residual}'")
        
        base_name = f"{base_name_for_residual} - Residual"
        
        try:
            # Controlla se esiste già un inbound con questo nome
            if not self._find_matching_inbound_shipment(base_name, merchant_id):
                logger.info(f"[_generate_residual_name] ✅ Nome disponibile: '{base_name}'")
                return base_name
            
            # Se esiste, prova con numerazione progressiva
            counter = 2
            max_attempts = 20  # Limite di sicurezza
            
            while counter <= max_attempts:
                numbered_name = f"{base_name_for_residual} - Residual {counter}"
                if not self._find_matching_inbound_shipment(numbered_name, merchant_id):
                    logger.info(f"[_generate_residual_name] ✅ Nome disponibile: '{numbered_name}'")
                    return numbered_name
                counter += 1
            
            # Se tutti i nomi sono occupati, aggiungi timestamp
            import time
            timestamp = int(time.time())
            fallback_name = f"{base_name_for_residual} - Residual {timestamp}"
            logger.warning(f"[_generate_residual_name] ⚠️ Usando nome fallback con timestamp: '{fallback_name}'")
            return fallback_name
            
        except Exception as e:
            logger.error(f"[_generate_residual_name] ❌ Errore generazione nome: {str(e)}")
            # Fallback con timestamp in caso di errore
            import time
            timestamp = int(time.time())
            fallback_name = f"{base_name_for_residual} - Residual {timestamp}"
            logger.warning(f"[_generate_residual_name] ⚠️ Usando nome fallback per errore: '{fallback_name}'")
            return fallback_name
    
    def _create_residual_inbound_shipment(self, residual_name: str, inbound_shipment: Dict[str, Any], residual_items: List[Dict[str, Any]]) -> Optional[int]:
        """
        Crea un nuovo inbound shipment residual con gli items calcolati.
        
        Args:
            residual_name: Nome per il nuovo shipment residual
            inbound_shipment: Dati del shipment inbound originale
            residual_items: Lista degli items residuali da aggiungere
            
        Returns:
            ID del nuovo shipment creato o None se fallisce
        """
        try:
            logger.info(f"🚀 Creazione inbound residual '{residual_name}' con {len(residual_items)} items")
            
            # Step 1: Crea il nuovo shipment inbound
            logger.info(f"📋 Creazione inbound shipment con name='{residual_name}', warehouse_id={inbound_shipment['warehouse_id']}, merchant_id={inbound_shipment['team_id']}")
            
            create_response = self.client.create_inbound_shipment(
                name=residual_name,
                warehouse_id=inbound_shipment['warehouse_id'],
                notes="Inbound residual creato automaticamente dal sistema",
                merchant_id=inbound_shipment['team_id']
            )
            
            # Il client completo restituisce un response object con shipment_id
            residual_shipment_id = create_response.shipment_id
            logger.info(f"✅ Inbound shipment creato con ID: {residual_shipment_id}")
            
            # Step 2: Aggiungi tutti gli items al shipment
            items_added = 0
            items_failed = 0
            
            for item in residual_items:
                try:
                    logger.info(f"➕ Aggiunta item {item['item_id']} con quantità {item['expected_quantity']}")
                    
                    self.client.add_item_to_shipment(
                        shipment_id=residual_shipment_id,
                        item_id=item['item_id'],
                        quantity=item['expected_quantity'],
                        merchant_id=inbound_shipment['team_id']
                    )
                    
                    logger.info(f"✅ Item {item['item_id']} aggiunto con quantità expected: {item['expected_quantity']}")
                    items_added += 1
                    
                except Exception as e:
                    logger.error(f"❌ Errore aggiunta item {item['item_id']}: {e}")
                    items_failed += 1
                    continue
            
            # Step 3: Log risultati aggiunta items
            logger.info(f"📊 Aggiunta items completata:")
            logger.info(f"    ✅ Items aggiunti: {items_added}")
            logger.info(f"    ❌ Items falliti: {items_failed}")
            logger.info(f"    📦 Totale items: {len(residual_items)}")
            
            # Step 4: Submit il shipment con carrier NO_TRACKING
            try:
                logger.info(f"📤 Submit shipment {residual_shipment_id} con carrier NO_TRACKING")
                
                self.client.submit_inbound_shipment(
                    shipment_id=residual_shipment_id,
                    carrier=Carrier.NO_TRACKING
                )
                
                logger.info(f"✅ Shipment {residual_shipment_id} submitted con successo")
                
                # Step 5: Aggiorna le quantità actual degli items (marca come ricevuti)
                for item in residual_items:
                    try:
                        # Usa il metodo del client completo per aggiornare le quantità
                        from libs.prepbusiness.models import ExpectedItemUpdate, ActualItemUpdate
                        
                        expected_update = ExpectedItemUpdate(
                            quantity=item['expected_quantity'],
                            item_group_configurations=[]
                        )
                        
                        actual_update = ActualItemUpdate(
                            quantity=item['actual_quantity'],
                            item_group_configurations=[]
                        )
                        
                        self.client.update_shipment_item(
                            shipment_id=residual_shipment_id,
                            item_id=item['item_id'],
                            expected=expected_update,
                            actual=actual_update,
                            merchant_id=inbound_shipment['team_id']
                        )
                        
                        logger.info(f"✅ Item {item['item_id']} aggiornato: actual={item['actual_quantity']}")
                        
                    except Exception as e:
                        logger.error(f"❌ Errore aggiornamento quantità item {item['item_id']}: {e}")
                        continue
                        
                logger.info(f"✅ Tutti gli items marcati come ricevuti")
                
            except Exception as e:
                logger.error(f"❌ Errore submit shipment {residual_shipment_id}: {e}")
                logger.warning(f"⚠️ Shipment creato ma non submitted - items non ricevuti")
            
            logger.info(f"🎉 SUCCESS: Inbound residual creato con {items_added} items - ID: {residual_shipment_id}")
            return residual_shipment_id
            
        except Exception as e:
            logger.error(f"❌ Errore creazione inbound residual: {e}")
            return None 