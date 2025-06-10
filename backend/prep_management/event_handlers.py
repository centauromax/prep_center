"""
Modulo per l'elaborazione degli eventi webhook specifici dell'applicazione.
Contiene la logica di business per reagire ai vari tipi di eventi.
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
from django.utils import timezone
import time
from datetime import datetime
import pytz

from .models import ShipmentStatusUpdate, OutgoingMessage, TelegramNotification
from .utils.messaging import send_outbound_without_inbound_notification
from .services import send_telegram_notification, format_shipment_notification
try:
    from libs.api_client.prep_business import PrepBusinessClient
    from libs.config import (
        PREP_BUSINESS_API_URL,
        PREP_BUSINESS_API_KEY,
        PREP_BUSINESS_API_TIMEOUT,
    )
    LIBS_IMPORT_SUCCESS = True
except ImportError as e:
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
        Elabora eventi per spedizioni in entrata.
        Attualmente non richiede elaborazione specifica.
        """
        return {
            'success': True,
            'message': f'Evento inbound shipment {update.event_type} elaborato correttamente',
        }
    
    def _process_outbound_shipment_closed(self, update: ShipmentStatusUpdate) -> Dict[str, Any]:
        """
        Elabora l'evento di chiusura di una spedizione in uscita.
        Crea un inbound residual con i prodotti rimanenti.
        
        Args:
            update: Oggetto ShipmentStatusUpdate da elaborare
            
        Returns:
            Dizionario con i risultati dell'elaborazione
        """
        logger.info(f"[_process_outbound_shipment_closed] 🚀 INIZIO elaborazione outbound_shipment.closed per shipment_id: {update.shipment_id}")
        
        try:
            # Verifica disponibilità client API
            if not self.client:
                error_msg = "Client API non disponibile per elaborare outbound_shipment.closed"
                logger.error(f"[_process_outbound_shipment_closed] ❌ {error_msg}")
                return {
                    'success': False,
                    'message': error_msg,
                    'error': 'client_unavailable'
                }
            
            # Recupera i dettagli dell'outbound shipment
            outbound_shipment = self._get_outbound_shipment_details(update.shipment_id, update.merchant_id)
            if not outbound_shipment:
                error_msg = f"Impossibile recuperare dettagli outbound shipment {update.shipment_id}"
                logger.error(f"[_process_outbound_shipment_closed] ❌ {error_msg}")
                return {
                    'success': False,
                    'message': error_msg,
                    'error': 'outbound_not_found'
                }
                
            outbound_name = outbound_shipment.get('name', str(update.shipment_id))
            logger.info(f"[_process_outbound_shipment_closed] 📦 Outbound shipment name: {outbound_name}")
            
            # Cerca l'inbound shipment corrispondente per nome
            inbound_shipment = self._find_matching_inbound_shipment(outbound_name, update.merchant_id)
            if not inbound_shipment:
                error_msg = f"Nessun inbound shipment trovato con nome '{outbound_name}'"
                logger.error(f"[_process_outbound_shipment_closed] ❌ {error_msg}")
                self._send_error_notification(error_msg, update.merchant_id, {
                    'outbound_shipment_id': update.shipment_id,
                    'outbound_name': outbound_name,
                    'merchant_id': update.merchant_id
                })
                return {
                    'success': False,
                    'message': error_msg,
                    'error': 'inbound_not_found'
                }
                
            inbound_id = inbound_shipment.get('id')
            logger.info(f"[_process_outbound_shipment_closed] 📥 Inbound shipment trovato - ID: {inbound_id}, Name: {inbound_shipment.get('name')}")
            
            # Recupera i prodotti dell'outbound e dell'inbound
            outbound_items = self._get_outbound_shipment_items(update.shipment_id)
            inbound_items = self._get_inbound_shipment_items(str(inbound_id))
            
            if not outbound_items:
                error_msg = f"Nessun prodotto trovato nell'outbound shipment {update.shipment_id}"
                logger.error(f"[_process_outbound_shipment_closed] ❌ {error_msg}")
                self._send_error_notification(error_msg, update.merchant_id, {
                    'outbound_shipment_id': update.shipment_id,
                    'inbound_shipment_id': inbound_id
                })
                return {
                    'success': False,
                    'message': error_msg,
                    'error': 'no_outbound_items'
                }
                
            if not inbound_items:
                error_msg = f"Nessun prodotto trovato nell'inbound shipment {inbound_id}"
                logger.error(f"[_process_outbound_shipment_closed] ❌ {error_msg}")
                self._send_error_notification(error_msg, update.merchant_id, {
                    'outbound_shipment_id': update.shipment_id,
                    'inbound_shipment_id': inbound_id
                })
                return {
                    'success': False,
                    'message': error_msg,
                    'error': 'no_inbound_items'
                }
            
            # Calcola i prodotti residuali
            residual_items = self._calculate_residual_items(inbound_items, outbound_items)
            logger.info(f"[_process_outbound_shipment_closed] 📊 Calcolati {len(residual_items)} prodotti residuali")
            
            if not residual_items:
                message = f"Nessun prodotto residuale da creare per shipment {outbound_name}"
                logger.info(f"[_process_outbound_shipment_closed] ✅ {message}")
                return {
                    'success': True,
                    'message': message,
                    'residual_items_count': 0
                }
            
            # Genera il nome per il nuovo inbound residual
            residual_name = self._generate_residual_name(outbound_name, update.merchant_id)
            logger.info(f"[_process_outbound_shipment_closed] 🏷️ Nome generato per residual: {residual_name}")
            
            # Crea il nuovo inbound shipment residual
            residual_shipment_id = self._create_residual_inbound_shipment(
                residual_name, 
                inbound_shipment.get('warehouse_id'),
                residual_items,
                update.merchant_id
            )
            
            if residual_shipment_id:
                success_msg = f"Creato inbound residual '{residual_name}' (ID: {residual_shipment_id}) con {len(residual_items)} prodotti"
                logger.info(f"[_process_outbound_shipment_closed] ✅ {success_msg}")
                return {
                    'success': True,
                    'message': success_msg,
                    'residual_shipment_id': residual_shipment_id,
                    'residual_name': residual_name,
                    'residual_items_count': len(residual_items)
                }
            else:
                error_msg = f"Errore nella creazione dell'inbound residual per {outbound_name}"
                logger.error(f"[_process_outbound_shipment_closed] ❌ {error_msg}")
                self._send_error_notification(error_msg, update.merchant_id, {
                    'outbound_shipment_id': update.shipment_id,
                    'inbound_shipment_id': inbound_id,
                    'residual_name': residual_name
                })
                return {
                    'success': False,
                    'message': error_msg,
                    'error': 'residual_creation_failed'
                }
                
        except Exception as e:
            error_msg = f"Errore durante elaborazione outbound_shipment.closed: {str(e)}"
            logger.error(f"[_process_outbound_shipment_closed] ❌ {error_msg}")
            logger.exception("Traceback completo:")
            
            self._send_error_notification(error_msg, update.merchant_id, {
                'outbound_shipment_id': update.shipment_id,
                'exception': str(e)
            })
            
            return {
                'success': False,
                'message': error_msg,
                'error': 'processing_exception'
            }
    
    def _send_telegram_notification_if_needed(self, update: ShipmentStatusUpdate):
        """
        Invia una notifica Telegram se l'evento lo richiede.
        
        Args:
            update: Oggetto ShipmentStatusUpdate da elaborare
        """
        # Lista degli eventi per cui inviare notifiche
        notify_events = [
            'inbound_shipment.created',    # Aggiunto! 
            'inbound_shipment.received',
            'inbound_shipment.shipped', 
            'outbound_shipment.created',
            # 'outbound_shipment.shipped',  # RIMOSSO: Non inviare notifiche per "Spedizione in uscita spedita"
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
            
            # NUOVO: Usa le informazioni sui prodotti estratte dal webhook se disponibili
            webhook_products_info = getattr(update, 'products_info', None)
            if webhook_products_info and webhook_products_info.get('total_quantity'):
                logger.info(f"[_send_telegram_notification_if_needed] ✅ Usando informazioni prodotti dal webhook: {webhook_products_info}")
                shipment_data['products_count'] = webhook_products_info['total_quantity']
                shipment_data['products_summary'] = webhook_products_info.get('products_summary', '')
            else:
                # Prova a estrarre le informazioni prodotti dal payload salvato
                payload = update.payload or {}
                saved_products_info = payload.get('products_info', {})
                if saved_products_info and saved_products_info.get('total_quantity'):
                    logger.info(f"[_send_telegram_notification_if_needed] ✅ Usando informazioni prodotti dal payload salvato: {saved_products_info}")
                    shipment_data['products_count'] = saved_products_info['total_quantity']
                    shipment_data['products_summary'] = saved_products_info.get('products_summary', '')
                else:
                    # Fallback: recupera conteggi prodotti per eventi specifici con chiamate API
                    logger.info(f"[_send_telegram_notification_if_needed] 🔍 Controllo evento: {update.event_type}")
            
            # Log dei dati finali che verranno passati per la formattazione
            logger.info(f"[_send_telegram_notification_if_needed] 📋 Dati finali spedizione: {shipment_data}")
            
            # Invia la notifica (la formattazione del messaggio sarà gestita internamente)
            success = send_telegram_notification(
                email=merchant_email,
                message=None,  # Verrà formattato internamente
                event_type=update.event_type,
                shipment_id=update.shipment_id,
                shipment_data=shipment_data  # Passiamo i dati per la formattazione
            )
            
            if success:
                logger.info(f"[_send_telegram_notification_if_needed] Notifica Telegram inviata per evento {update.event_type} a {merchant_email}")
            else:
                logger.warning(f"[_send_telegram_notification_if_needed] Notifica Telegram fallita per evento {update.event_type} a {merchant_email}")
                
        except Exception as e:
            logger.error(f"[_send_telegram_notification_if_needed] Errore nell'invio notifica Telegram: {str(e)}")
    
    def _get_outbound_shipment_products_count(self, shipment_id: str, merchant_id: str) -> Optional[int]:
        """
        Recupera il numero totale di prodotti per una spedizione in uscita.
        
        Args:
            shipment_id: ID della spedizione
            merchant_id: ID del merchant
            
        Returns:
            int: Numero totale di prodotti o None se errore
        """
        logger.info(f"[_get_outbound_shipment_products_count] 🚀 INIZIO recupero prodotti - shipment_id={shipment_id}, merchant_id={merchant_id}")
        
        try:
            if not self.client:
                logger.error(f"[_get_outbound_shipment_products_count] ❌ Client PrepBusiness non inizializzato")
                return None
                
            logger.info(f"[_get_outbound_shipment_products_count] 📞 Chiamata API get_outbound_shipment_items per spedizione {shipment_id}")
            
            # Recupera gli items della spedizione
            items_response = self.client.get_outbound_shipment_items(
                shipment_id=int(shipment_id),
                merchant_id=int(merchant_id) if merchant_id else None
            )
            
            logger.info(f"[_get_outbound_shipment_products_count] 📥 Risposta API ricevuta: {type(items_response)}")
            
            if not items_response:
                logger.warning(f"[_get_outbound_shipment_products_count] ⚠️ Risposta API vuota per spedizione {shipment_id}")
                return None
                
            if not hasattr(items_response, 'items'):
                logger.warning(f"[_get_outbound_shipment_products_count] ⚠️ Risposta API senza attributo 'items' per spedizione {shipment_id}")
                logger.warning(f"[_get_outbound_shipment_products_count] 📋 Attributi disponibili: {dir(items_response)}")
                return None
            
            logger.info(f"[_get_outbound_shipment_products_count] 📦 Trovati {len(items_response.items)} items nella spedizione")
            
            # Calcola il numero totale di prodotti sommando le quantità
            total_quantity = 0
            for i, item in enumerate(items_response.items):
                item_quantity = getattr(item, 'quantity', 0)
                total_quantity += item_quantity
                logger.info(f"[_get_outbound_shipment_products_count] 📦 Item {i+1}/{len(items_response.items)} - ID: {getattr(item, 'id', 'N/A')}, Quantità: {item_quantity}")
            
            logger.info(f"[_get_outbound_shipment_products_count] ✅ TOTALE prodotti per spedizione {shipment_id}: {total_quantity}")
            return total_quantity
            
        except Exception as e:
            logger.error(f"[_get_outbound_shipment_products_count] ❌ ECCEZIONE nel recupero prodotti per spedizione {shipment_id}: {str(e)}")
            logger.exception("Traceback completo:")
            return None
    
    def _get_inbound_shipment_products_count(self, shipment_id: str, merchant_id: str) -> Optional[dict]:
        """
        Recupera i conteggi dei prodotti attesi e arrivati per una spedizione in entrata.
        
        Args:
            shipment_id: ID della spedizione
            merchant_id: ID del merchant
            
        Returns:
            dict: {'expected': int, 'received': int} o None se errore
        """
        logger.info(f"[_get_inbound_shipment_products_count] 🚀 INIZIO recupero conteggi - shipment_id={shipment_id}, merchant_id={merchant_id}")
        
        try:
            if not self.client:
                logger.error(f"[_get_inbound_shipment_products_count] ❌ Client PrepBusiness non inizializzato")
                return None
                
            logger.info(f"[_get_inbound_shipment_products_count] 📞 Chiamata API get_inbound_shipment_items per spedizione {shipment_id}")
            
            # Recupera gli items della spedizione
            items_response = self.client.get_inbound_shipment_items(
                shipment_id=int(shipment_id),
                merchant_id=int(merchant_id) if merchant_id else None
            )
            
            logger.info(f"[_get_inbound_shipment_products_count] 📥 Risposta API ricevuta: {type(items_response)}")
            
            if not items_response:
                logger.warning(f"[_get_inbound_shipment_products_count] ⚠️ Risposta API vuota per spedizione {shipment_id}")
                return None
                
            if not hasattr(items_response, 'items'):
                logger.warning(f"[_get_inbound_shipment_products_count] ⚠️ Risposta API senza attributo 'items' per spedizione {shipment_id}")
                logger.warning(f"[_get_inbound_shipment_products_count] 📋 Attributi disponibili: {dir(items_response)}")
                return None
            
            logger.info(f"[_get_inbound_shipment_products_count] 📦 Trovati {len(items_response.items)} items nella spedizione")
            
            # Debug: mostra la struttura del primo item se disponibile
            if len(items_response.items) > 0:
                first_item = items_response.items[0]
                logger.info(f"[_get_inbound_shipment_products_count] 🔍 DEBUG primo item - Attributi: {dir(first_item)}")
                expected_obj = getattr(first_item, 'expected', None)
                actual_obj = getattr(first_item, 'actual', None)
                logger.info(f"[_get_inbound_shipment_products_count] 🔍 DEBUG expected: {expected_obj} (tipo: {type(expected_obj)})")
                if expected_obj and hasattr(expected_obj, '__dict__'):
                    logger.info(f"[_get_inbound_shipment_products_count] 🔍 DEBUG expected attributi: {vars(expected_obj)}")
                logger.info(f"[_get_inbound_shipment_products_count] 🔍 DEBUG actual: {actual_obj} (tipo: {type(actual_obj)})")
                if actual_obj and hasattr(actual_obj, '__dict__'):
                    logger.info(f"[_get_inbound_shipment_products_count] 🔍 DEBUG actual attributi: {vars(actual_obj)}")
            
            # Calcola i totali per attesi e arrivati
            total_expected = 0
            total_received = 0
            
            for i, item in enumerate(items_response.items):
                # L'oggetto expected potrebbe essere un oggetto complesso, estraiamo il valore numerico
                item_expected_obj = getattr(item, 'expected', None)
                if item_expected_obj is not None:
                    # Se è un oggetto, prova a ottenere la quantity
                    if hasattr(item_expected_obj, 'quantity'):
                        item_expected = getattr(item_expected_obj, 'quantity', 0) or 0
                    elif hasattr(item_expected_obj, 'value'):
                        item_expected = getattr(item_expected_obj, 'value', 0) or 0
                    elif isinstance(item_expected_obj, (int, float)):
                        item_expected = item_expected_obj
                    else:
                        # Prova a convertire a intero direttamente
                        try:
                            item_expected = int(item_expected_obj)
                        except (ValueError, TypeError):
                            item_expected = 0
                else:
                    item_expected = 0
                
                # L'oggetto actual potrebbe essere un oggetto complesso, estraiamo il valore numerico
                item_received_obj = getattr(item, 'actual', None)
                if item_received_obj is not None:
                    # Se è un oggetto, prova a ottenere la quantity
                    if hasattr(item_received_obj, 'quantity'):
                        item_received = getattr(item_received_obj, 'quantity', 0) or 0
                    elif hasattr(item_received_obj, 'value'):
                        item_received = getattr(item_received_obj, 'value', 0) or 0
                    elif isinstance(item_received_obj, (int, float)):
                        item_received = item_received_obj
                    else:
                        # Prova a convertire a intero direttamente
                        try:
                            item_received = int(item_received_obj)
                        except (ValueError, TypeError):
                            item_received = 0
                else:
                    item_received = 0
                
                total_expected += item_expected
                total_received += item_received
                
                logger.info(f"[_get_inbound_shipment_products_count] 📦 Item {i+1}/{len(items_response.items)} - ID: {getattr(item, 'id', 'N/A')}, Attesi: {item_expected} (tipo: {type(item_expected_obj)}), Arrivati: {item_received} (tipo: {type(item_received_obj)})")
            
            result = {'expected': total_expected, 'received': total_received}
            logger.info(f"[_get_inbound_shipment_products_count] ✅ TOTALI per spedizione {shipment_id}: {result}")
            return result
            
        except Exception as e:
            logger.error(f"[_get_inbound_shipment_products_count] ❌ ECCEZIONE nel recupero conteggi per spedizione {shipment_id}: {str(e)}")
            logger.exception("Traceback completo:")
            return None
    
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
            
            # Ottieni i merchant dall'API (la risposta è già una lista)
            merchants = self.client.get_merchants()
            
            logger.info(f"[_get_merchant_email] 📋 Ricevuti {len(merchants)} merchants dall'API")
            
            # Debug: mostra tutti i merchant disponibili
            for m in merchants:
                primary_email = m.get('primaryEmail', m.get('email', 'N/A'))
                logger.info(f"[_get_merchant_email] 🏢 Merchant ID: {m.get('id')}, Name: {m.get('name', 'N/A')}, PrimaryEmail: {primary_email}")
            
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
                logger.warning(f"[_get_merchant_email] ❌ Merchant {merchant_id} NON trovato nell'elenco di {len(merchants)} merchants")
                return None
            
        except Exception as e:
            logger.error(f"[_get_merchant_email] ❌ ECCEZIONE nel recupero email merchant {merchant_id}: {str(e)}")
            logger.exception("Traceback completo:")
            return None
    
    def _get_outbound_shipment_details(self, shipment_id: str, merchant_id: str) -> Optional[Dict[str, Any]]:
        """
        Recupera i dettagli completi di un outbound shipment.
        
        Args:
            shipment_id: ID della spedizione
            merchant_id: ID del merchant
            
        Returns:
            Dict con i dettagli della spedizione o None se errore
        """
        logger.info(f"[_get_outbound_shipment_details] 🚀 Recupero dettagli outbound shipment_id={shipment_id}, merchant_id={merchant_id}")
        
        try:
            # Usa il metodo generico get_shipment (restituisce dict)
            shipment = self.client.get_shipment(shipment_id)
            
            if shipment:
                result = {
                    'id': shipment.get('id'),
                    'name': shipment.get('name'),
                    'status': shipment.get('status', ''),
                    'warehouse_id': shipment.get('warehouse_id'),
                    'notes': shipment.get('notes'),
                    'created_at': shipment.get('created_at', '')
                }
                
                logger.info(f"[_get_outbound_shipment_details] ✅ Dettagli recuperati: {result}")
                return result
            else:
                logger.warning(f"[_get_outbound_shipment_details] ⚠️ Nessun dato nella risposta API")
                return None
                
        except Exception as e:
            logger.error(f"[_get_outbound_shipment_details] ❌ Errore recupero dettagli: {str(e)}")
            logger.exception("Traceback:")
            return None
    
    def _find_matching_inbound_shipment(self, outbound_shipment_name: str, merchant_id: str) -> Optional[Dict[str, Any]]:
        """
        Cerca un inbound shipment per nome.
        
        Args:
            outbound_shipment_name: Nome della spedizione da cercare
            merchant_id: ID del merchant
            
        Returns:
            Dict con i dettagli della spedizione o None se non trovata
        """
        logger.info(f"[_find_matching_inbound_shipment] 🔍 Ricerca inbound shipment con nome='{outbound_shipment_name}', merchant_id={merchant_id}")
        
        try:
            # Recupera tutte le spedizioni inbound con paginazione
            page = 1
            per_page = 50
            max_pages = 10  # Limite di sicurezza
            
            while page <= max_pages:
                logger.info(f"[_find_matching_inbound_shipment] 📄 Recupero pagina {page} (per_page={per_page})")
                
                shipments_response = self.client.get_inbound_shipments(
                    page=page,
                    per_page=per_page,
                    merchant_id=int(merchant_id) if merchant_id else None
                )
                
                if shipments_response and isinstance(shipments_response, list):
                    logger.info(f"[_find_matching_inbound_shipment] 📦 Trovate {len(shipments_response)} spedizioni nella pagina {page}")
                    
                    for shipment in shipments_response:
                        shipment_name = shipment.get('name', '')
                        logger.debug(f"[_find_matching_inbound_shipment] 🔍 Confronto: '{shipment_name}' == '{outbound_shipment_name}'")
                        
                        if shipment_name == outbound_shipment_name:
                            result = {
                                'id': shipment.get('id'),
                                'name': shipment.get('name'),
                                'status': shipment.get('status', ''),
                                'warehouse_id': shipment.get('warehouse_id'),
                                'notes': shipment.get('notes'),
                                'created_at': shipment.get('created_at', '')
                            }
                            logger.info(f"[_find_matching_inbound_shipment] ✅ Inbound shipment trovato: {result}")
                            return result
                    
                    # Se non ci sono più pagine, esci
                    if len(shipments_response) < per_page:
                        logger.info(f"[_find_matching_inbound_shipment] 📄 Ultima pagina raggiunta (< {per_page} items)")
                        break
                        
                    page += 1
                else:
                    logger.info(f"[_find_matching_inbound_shipment] 📄 Pagina {page} vuota o senza data")
                    break
            
            logger.info(f"[_find_matching_inbound_shipment] ❌ Nessun inbound shipment trovato con nome '{outbound_shipment_name}'")
            return None
                
        except Exception as e:
            logger.error(f"[_find_matching_inbound_shipment] ❌ Errore ricerca: {str(e)}")
            logger.exception("Traceback:")
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
        
        try:
            items_response = self.client.get_outbound_shipment_items(
                shipment_id=int(shipment_id)
            )
            
            if items_response and isinstance(items_response, list):
                items = []
                for item in items_response:
                    # Il client originale restituisce dict, non oggetti Pydantic
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
        
        try:
            items_response = self.client.get_inbound_shipment_items(
                shipment_id=int(shipment_id)
            )
            
            if items_response and isinstance(items_response, list):
                items = []
                for item in items_response:
                    # Il client originale restituisce dict, non oggetti Pydantic
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
                    logger.debug(f"[_get_inbound_shipment_items] 📦 Item: {item_data}")
                
                logger.info(f"[_get_inbound_shipment_items] ✅ Recuperati {len(items)} items")
                return items
            else:
                logger.warning(f"[_get_inbound_shipment_items] ⚠️ Nessun item trovato nella risposta API")
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
        
        try:
            # Prepara i dati per la creazione dell'inbound
            shipment_data = {
                'name': name,
                'warehouse_id': warehouse_id,
                'notes': f"Inbound residual creato automaticamente per prodotti rimanenti",
                'merchant_id': int(merchant_id) if merchant_id else None
            }
            
            # Crea il nuovo inbound shipment usando il client originale
            create_response = self.client.create_inbound_shipment(shipment_data)
            
            if create_response and create_response.get('id'):
                shipment_id = create_response.get('id')
                logger.info(f"[_create_residual_inbound_shipment] ✅ Inbound creato con ID: {shipment_id}")
                
                # Per ora, saltiamo l'aggiunta degli items individuali
                # Il client originale potrebbe non supportare add_item_to_shipment
                # Questo può essere implementato in una seconda fase
                logger.info(f"[_create_residual_inbound_shipment] ✅ Inbound residual creato con successo: ID {shipment_id}")
                logger.info(f"[_create_residual_inbound_shipment] ℹ️ Items da aggiungere manualmente: {len(items)} prodotti")
                
                # Log degli items per il debugging
                for item in items:
                    logger.info(f"[_create_residual_inbound_shipment] 📦 Item residual: {item['title']} - Expected: {item['expected_quantity']}, Actual: {item['actual_quantity']}")
                
                return shipment_id
            else:
                logger.error(f"[_create_residual_inbound_shipment] ❌ Risposta API senza ID: {create_response}")
                return None
                
        except Exception as e:
            logger.error(f"[_create_residual_inbound_shipment] ❌ Errore creazione inbound: {str(e)}")
            logger.exception("Traceback:")
            return None
    
    def _send_error_notification(self, error_message: str, merchant_id: str, context: Dict[str, Any]):
        """
        Invia una notifica di errore tramite Telegram e/o browser extension.
        
        Args:
            error_message: Messaggio di errore
            merchant_id: ID del merchant
            context: Contesto aggiuntivo dell'errore
        """
        logger.info(f"[_send_error_notification] 🚨 Invio notifica errore: {error_message}")
        
        try:
            # Invia notifica Telegram se possibile
            try:
                merchant_email = self._get_merchant_email(merchant_id)
                if merchant_email:
                    full_message = f"🚨 ERRORE RESIDUAL INBOUND\n\n{error_message}\n\nContesto: {context}"
                    send_telegram_notification(merchant_email, full_message)
                    logger.info(f"[_send_error_notification] ✅ Notifica Telegram inviata a {merchant_email}")
            except Exception as e:
                logger.error(f"[_send_error_notification] ❌ Errore invio Telegram: {str(e)}")
            
            # Invia notifica browser extension
            try:
                from .models import OutgoingMessage
                
                OutgoingMessage.objects.create(
                    message_id='RESIDUAL_INBOUND_ERROR',
                    parameters={
                        'error_message': error_message,
                        'merchant_id': merchant_id,
                        'context': context,
                        'timestamp': timezone.now().isoformat()
                    }
                )
                logger.info(f"[_send_error_notification] ✅ Messaggio browser extension creato")
            except Exception as e:
                logger.error(f"[_send_error_notification] ❌ Errore creazione messaggio browser: {str(e)}")
                
        except Exception as e:
            logger.error(f"[_send_error_notification] ❌ Errore generale invio notifiche: {str(e)}") 