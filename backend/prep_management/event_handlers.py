"""
Modulo per l'elaborazione degli eventi webhook specifici dell'applicazione.
Contiene la logica di business per reagire ai vari tipi di eventi.
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
from django.utils import timezone
import time

from .models import ShipmentStatusUpdate, OutgoingMessage
from .utils.messaging import send_outbound_without_inbound_notification
from .services import send_telegram_notification, format_shipment_notification
from libs.prepbusiness.client import PrepBusinessClient
from libs.config import (
    PREP_BUSINESS_API_URL,
    PREP_BUSINESS_API_KEY,
    PREP_BUSINESS_API_TIMEOUT,
)

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
        domain = PREP_BUSINESS_API_URL.replace('https://', '').replace('http://', '').split('/')[0]
        logger.info(f"[WebhookEventProcessor.__init__] Dominio calcolato per il client: {domain}")
        
        # Riattivo il client per le chiamate API reali
        try:
            logger.info("[WebhookEventProcessor.__init__] Tentativo di istanziare PrepBusinessClient.")
            self.client = PrepBusinessClient(
                api_key=PREP_BUSINESS_API_KEY,
                company_domain=domain,
                timeout=PREP_BUSINESS_API_TIMEOUT,
            )
            logger.info("[WebhookEventProcessor.__init__] PrepBusinessClient istanziato con successo.")
        except Exception as e_client_init:
            logger.error(f"[WebhookEventProcessor.__init__] Eccezione durante l'istanza di PrepBusinessClient: " + str(e_client_init))
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
                    'message': f'Aggiornamento già elaborato in precedenza',
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
            logger.error(f"[WebhookEventProcessor.process_event] Eccezione durante process_event per Update ID: {update_id}. Errore: {str(e)}")
            logger.exception("Traceback completo:")
            
            # Aggiorna il record con l'errore
            try:
                logger.info(f"[WebhookEventProcessor.process_event] Tentativo salvataggio errore per Update ID: {update_id}.")
                update.processed = True
                update.processed_at = timezone.now()
                update.process_success = False
                update.process_message = f"Errore: {str(e)}"
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
                'message': f'Errore durante l\'elaborazione: {str(e)}',
                'error': 'processing_exception'
            }
    
    def _process_outbound_shipment_created(self, update: ShipmentStatusUpdate) -> Dict[str, Any]:
        """
        Elabora l'evento di creazione di una spedizione in uscita.
        Verifica che esista una spedizione in entrata con lo stesso nome.
        
        Args:
            update: Oggetto ShipmentStatusUpdate da elaborare
            
        Returns:
            Dizionario con i risultati dell'elaborazione
        """
        shipment_id = update.shipment_id
        merchant_id = update.merchant_id
        payload = update.payload or {}
        
        # Estrai il nome della spedizione
        data = payload.get('data', {})
        shipment_name = data.get('name', '')
        
        if not shipment_name:
            return {
                'success': False,
                'message': 'Nome spedizione non trovato nei dati ricevuti',
                'error': 'missing_shipment_name'
            }
        
        try:
            # Verifica che self.client sia disponibile
            if self.client is None:
                logger.error("[_process_outbound_shipment_created] Client API non disponibile!")
                return {
                    'success': False,
                    'message': 'Client API non disponibile per controllare spedizioni inbound',
                    'error': 'client_unavailable'
                }
            
            # Ottieni tutte le spedizioni in entrata per questo merchant usando l'API reale
            logger.info(f"[_process_outbound_shipment_created] Chiamata API get_inbound_shipments per merchant {merchant_id}...")
            start_time_inbound = time.time()
            
            try:
                # Aumento per_page per essere sicuri di non perdere spedizioni
                inbound_shipments_response = self.client.get_inbound_shipments(
                    merchant_id=merchant_id, 
                    per_page=100
                )
                logger.info(f"[_process_outbound_shipment_created] API get_inbound_shipments chiamata con successo")
            except Exception as e_api:
                logger.error(f"[_process_outbound_shipment_created] ERRORE nella chiamata API get_inbound_shipments: {str(e_api)}")
                logger.exception("Traceback della chiamata API:")
                return {
                    'success': False,
                    'message': f'Errore nella chiamata API per spedizioni inbound: {str(e_api)}',
                    'error': 'api_call_failed'
                }
            
            end_time_inbound = time.time()
            logger.info(f"[_process_outbound_shipment_created] Chiamata API get_inbound_shipments completata in {end_time_inbound - start_time_inbound:.2f} secondi.")
            
            # Verifica la risposta
            if not inbound_shipments_response:
                logger.warning("[_process_outbound_shipment_created] Risposta API vuota!")
                return {
                    'success': False,
                    'message': 'Risposta API vuota per spedizioni inbound',
                    'error': 'empty_api_response'
                }
            
            inbound_shipments = inbound_shipments_response.data if inbound_shipments_response else []
            logger.info(f"[_process_outbound_shipment_created] Ricevute {len(inbound_shipments)} spedizioni in entrata grezze.")
            
            # Log di alcuni esempi delle spedizioni ricevute
            if len(inbound_shipments) > 0:
                logger.info(f"[_process_outbound_shipment_created] Esempio prima spedizione: ID={inbound_shipments[0].id}, nome='{inbound_shipments[0].name}', archived_at={inbound_shipments[0].archived_at}")
            
            # Filtra solo le spedizioni in entrata non archiviate
            active_inbound_shipments = [s for s in inbound_shipments if s.archived_at is None]
            logger.info(f"[_process_outbound_shipment_created] {len(active_inbound_shipments)} spedizioni in entrata non archiviate.")
            
            # Log dei nomi delle spedizioni inbound per debug
            inbound_names = [s.name for s in active_inbound_shipments]
            logger.info(f"[_process_outbound_shipment_created] Nomi spedizioni inbound attive: {inbound_names}")
            logger.info(f"[_process_outbound_shipment_created] Cerco corrispondenza CASE-INSENSITIVE per: '{shipment_name}'")
            
            # Cerca una spedizione con lo stesso nome (confronto case-insensitive)
            matching_shipment = next(
                (s for s in active_inbound_shipments if s.name.lower() == shipment_name.lower()), 
                None
            )
            
            if matching_shipment:
                logger.info(f"[_process_outbound_shipment_created] ✅ TROVATA corrispondenza: spedizione inbound ID {matching_shipment.id} con nome '{matching_shipment.name}'")
                return {
                    'success': True,
                    'message': f'Trovata spedizione in entrata corrispondente: {matching_shipment.id}',
                    'related_inbound_id': matching_shipment.id,
                    'related_inbound_status': matching_shipment.status,
                    'outbound_shipment_id': shipment_id,
                    'outbound_shipment_name': shipment_name
                }
            else:
                logger.warning(f"[_process_outbound_shipment_created] ❌ NESSUNA corrispondenza trovata per '{shipment_name}' tra le {len(active_inbound_shipments)} spedizioni inbound attive")
                
                # Recupera il nome del merchant
                merchant_name = update.merchant_name
                if not merchant_name and merchant_id:
                    try:
                        logger.info(f"[_process_outbound_shipment_created] Nome merchant non disponibile, chiamata API get_merchants...")
                        start_time_merchants = time.time()
                        
                        merchants_response = self.client.get_merchants()
                        
                        end_time_merchants = time.time()
                        logger.info(f"[_process_outbound_shipment_created] Chiamata API get_merchants completata in {end_time_merchants - start_time_merchants:.2f} secondi.")
                        merchants = merchants_response.data if merchants_response else []
                        merchant = next((m for m in merchants if str(m.id) == str(merchant_id)), None)
                        merchant_name = merchant.name if merchant else str(merchant_id)
                        logger.info(f"[_process_outbound_shipment_created] Nome merchant recuperato: {merchant_name}")
                    except Exception as e:
                        logger.error(f"[_process_outbound_shipment_created] Errore durante il recupero del nome del merchant via API: {str(e)}")
                        merchant_name = str(merchant_id)
                
                # Invia notifica per spedizione outbound senza corrispondente inbound
                logger.info(f"[_process_outbound_shipment_created] 🚨 Invio notifica OUTBOUND_WITHOUT_INBOUND per '{shipment_name}' (merchant: {merchant_name})")
                send_outbound_without_inbound_notification(merchant_name, shipment_name)
                return {
                    'success': False,
                    'message': f'Nessuna spedizione in entrata trovata con nome: {shipment_name}',
                    'error': 'missing_inbound_shipment',
                    'outbound_shipment_id': shipment_id,
                    'outbound_shipment_name': shipment_name
                }
                
        except Exception as e:
            logger.error(f"Errore nella ricerca di spedizioni in entrata: {str(e)}")
            return {
                'success': False,
                'message': f'Errore durante la verifica della spedizione in entrata: {str(e)}',
                'error': 'api_error'
            }
    
    def _process_inbound_shipment_event(self, update: ShipmentStatusUpdate) -> Dict[str, Any]:
        """
        Elabora eventi relativi a spedizioni in entrata.
        
        Args:
            update: Oggetto ShipmentStatusUpdate da elaborare
            
        Returns:
            Dizionario con i risultati dell'elaborazione
        """
        # Per ora, registra solamente l'evento
        event_type = update.event_type
        shipment_id = update.shipment_id
        
        return {
            'success': True,
            'message': f'Evento {event_type} per spedizione in entrata {shipment_id} registrato',
        } 

    def _send_telegram_notification_if_needed(self, update: ShipmentStatusUpdate):
        """
        Invia una notifica Telegram se l'evento lo richiede.
        
        Args:
            update: Oggetto ShipmentStatusUpdate da elaborare
        """
        # Lista degli eventi per cui inviare notifiche
        notify_events = [
            'inbound_shipment.received',
            'inbound_shipment.shipped', 
            'outbound_shipment.created',
            'outbound_shipment.shipped',
            'outbound_shipment.closed',
            'order.created',
            'order.shipped'
        ]
        
        # Controlla se l'evento richiede una notifica
        logger.info(f"[_send_telegram_notification_if_needed] 🔔 CONTROLLO NOTIFICA - Evento {update.event_type} per spedizione {update.shipment_id}")
        logger.info(f"[_send_telegram_notification_if_needed] Lista eventi che richiedono notifica: {notify_events}")
        
        if update.event_type not in notify_events:
            logger.info(f"[_send_telegram_notification_if_needed] ❌ Evento {update.event_type} NON richiede notifica Telegram")
            return
            
        logger.info(f"[_send_telegram_notification_if_needed] ✅ Evento {update.event_type} RICHIEDE notifica Telegram")
        
        try:
            # Estrai l'email del merchant dall'API PrepBusiness
            logger.info(f"[_send_telegram_notification_if_needed] 🔍 Recupero email per merchant_id: {update.merchant_id}")
            merchant_email = self._get_merchant_email(update.merchant_id)
            
            if not merchant_email:
                logger.warning(f"[_send_telegram_notification_if_needed] ❌ Email merchant NON trovata per ID: {update.merchant_id}")
                
                # Debug: mostra le email registrate in Telegram
                from .models import TelegramNotification
                registered_emails = list(TelegramNotification.objects.filter(is_active=True).values_list('email', flat=True))
                logger.warning(f"[_send_telegram_notification_if_needed] 📧 Email registrate in Telegram: {registered_emails}")
                return
                
            logger.info(f"[_send_telegram_notification_if_needed] ✅ Email merchant trovata: {merchant_email}")
            
            # Prepara i dati della spedizione
            payload = update.payload or {}
            data = payload.get('data', {})
            
            shipment_data = {
                'shipment_id': update.shipment_id,
                'shipment_name': data.get('name', ''),
                'tracking_number': update.tracking_number,
                'carrier': update.carrier,
                'notes': update.notes,
                'merchant_name': update.merchant_name,
                'new_status': update.new_status
            }
            
            # Formatta il messaggio
            message = format_shipment_notification(update.event_type, shipment_data)
            
            # Invia la notifica
            success = send_telegram_notification(
                email=merchant_email,
                message=message,
                event_type=update.event_type,
                shipment_id=update.shipment_id
            )
            
            if success:
                logger.info(f"[_send_telegram_notification_if_needed] Notifica Telegram inviata per evento {update.event_type} a {merchant_email}")
            else:
                logger.warning(f"[_send_telegram_notification_if_needed] Notifica Telegram fallita per evento {update.event_type} a {merchant_email}")
                
        except Exception as e:
            logger.error(f"[_send_telegram_notification_if_needed] Errore nell'invio notifica Telegram: {str(e)}")
    
    def _get_merchant_email(self, merchant_id: str) -> Optional[str]:
        """
        Recupera l'email di un merchant dall'API PrepBusiness.
        
        Args:
            merchant_id: ID del merchant
            
        Returns:
            Email del merchant o None se non trovata
        """
        if not self.client:
            logger.error(f"[_get_merchant_email] ❌ Client PrepBusiness non inizializzato")
            return None
            
        if not merchant_id:
            logger.error(f"[_get_merchant_email] ❌ Merchant ID vuoto")
            return None
            
        try:
            logger.info(f"[_get_merchant_email] 🔍 Chiamata API per recuperare merchants...")
            
            # Ottieni i merchant dall'API
            merchants_response = self.client.get_merchants()
            merchants = merchants_response.data if merchants_response else []
            
            logger.info(f"[_get_merchant_email] 📋 Ricevuti {len(merchants)} merchants dall'API")
            
            # Debug: mostra tutti i merchant disponibili
            for m in merchants:
                logger.info(f"[_get_merchant_email] 🏢 Merchant ID: {m.id}, Name: {getattr(m, 'name', 'N/A')}, Email: {getattr(m, 'email', 'N/A')}")
            
            # Trova il merchant con l'ID specificato
            merchant = next((m for m in merchants if str(m.id) == str(merchant_id)), None)
            
            if merchant:
                if hasattr(merchant, 'email') and merchant.email:
                    logger.info(f"[_get_merchant_email] ✅ Email trovata per merchant {merchant_id}: {merchant.email}")
                    return merchant.email
                else:
                    logger.warning(f"[_get_merchant_email] ❌ Merchant {merchant_id} trovato ma SENZA email (attributi: {dir(merchant)})")
                    return None
            else:
                logger.warning(f"[_get_merchant_email] ❌ Merchant {merchant_id} NON trovato nell'elenco di {len(merchants)} merchants")
                return None
                
        except Exception as e:
            logger.error(f"[_get_merchant_email] ❌ ECCEZIONE nel recupero email merchant {merchant_id}: {str(e)}")
            logger.exception("Traceback completo:")
            return None 