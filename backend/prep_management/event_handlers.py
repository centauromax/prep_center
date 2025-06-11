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
        """
        return {
            'success': True,
            'message': 'Evento outbound shipment closed elaborato',
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