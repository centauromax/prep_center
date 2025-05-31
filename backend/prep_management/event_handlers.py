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
        
        # INIZIALIZZAZIONE CLIENT COMMENTATA TEMPORANEAMENTE PER RISOLVERE ERRORE SYNTAX
        # try:
        #     logger.info("[WebhookEventProcessor.__init__] Tentativo di istanziare PrepBusinessClient.")
        #     self.client = PrepBusinessClient(
        #         api_key=PREP_BUSINESS_API_KEY,
        #         company_domain=domain,
        #         timeout=PREP_BUSINESS_API_TIMEOUT,
        #     )
        #     logger.info("[WebhookEventProcessor.__init__] PrepBusinessClient istanziato con successo.")
        # except Exception as e_client_init:
        #     logger.error(f"[WebhookEventProcessor.__init__] Eccezione durante l'istanza di PrepBusinessClient: " + str(e_client_init))
        #     self.client = None
        
        # Client disabilitato manualmente per evitare errori di sintassi
        self.client = None
        logger.info("[WebhookEventProcessor.__init__] Client disabilitato manualmente per debug")
        
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
            # Verifica che self.client sia stato inizializzato
            if self.client is None:
                logger.warning(f"[_process_outbound_shipment_created] Client non inizializzato, utilizzo dati mock.")
            
            # Ottieni tutte le spedizioni in entrata per questo merchant
            logger.info(f"[_process_outbound_shipment_created] Chiamata API get_inbound_shipments per merchant {merchant_id}...")
            start_time_inbound = time.time()
            # COMMENTO: Disabilitata la chiamata reale all'API PrepBusiness per evitare traffico durante lo sviluppo/test.
            # inbound_shipments_response = self.client.get_inbound_shipments(merchant_id=merchant_id)
            # Sostituito con dati mock:
            logger.info("[_process_outbound_shipment_created] Restituzione dati mock per get_inbound_shipments.")
            # Simula la struttura di InboundShipmentsResponse e InboundShipment come definito in libs/prepbusiness/models.py
            # class InboundShipment(BaseModel): id: int, name: str, archived_at: Optional[datetime], status: InboundShipmentStatus
            # class InboundShipmentsResponse(BaseModel): data: List[InboundShipment]
            
            # Mock per InboundShipment (assicurati che i campi essenziali ci siano)
            mock_inbound_shipment_1 = type('obj', (object,), {
                'id': 101, 
                'name': 'SPEDIZIONE_INBOUND_DIVERSA',  # Nome diverso per non trovare sempre corrispondenza
                'archived_at': None, 
                'status': 'open',
                # Aggiungi altri campi se necessari per la logica successiva
            })
            mock_inbound_shipment_2 = type('obj', (object,), {
                'id': 102, 
                'name': 'ALTRO_NOME_SPEDIZIONE_INBOUND', 
                'archived_at': None, 
                'status': 'open'
            })
            
            # Mock per InboundShipmentsResponse
            inbound_shipments_response = type('obj', (object,), {
                'data': [mock_inbound_shipment_1, mock_inbound_shipment_2]
            })
            
            end_time_inbound = time.time()
            logger.info(f"[_process_outbound_shipment_created] Chiamata API get_inbound_shipments (mock) completata in {end_time_inbound - start_time_inbound:.2f} secondi.")
            
            inbound_shipments = inbound_shipments_response.data if inbound_shipments_response else []
            logger.info(f"[_process_outbound_shipment_created] Ricevute {len(inbound_shipments)} spedizioni in entrata grezze.")
            
            # Filtra solo le spedizioni in entrata non archiviate
            inbound_shipments = [s for s in inbound_shipments if s.archived_at is None]
            logger.info(f"[_process_outbound_shipment_created] {len(inbound_shipments)} spedizioni in entrata non archiviate.")
            
            # Cerca una spedizione con lo stesso nome
            matching_shipment = next(
                (s for s in inbound_shipments if s.name == shipment_name), 
                None
            )
            
            if matching_shipment:
                return {
                    'success': True,
                    'message': f'Trovata spedizione in entrata corrispondente: {matching_shipment.id}',
                    'related_inbound_id': matching_shipment.id,
                    'related_inbound_status': matching_shipment.status,
                    'outbound_shipment_id': shipment_id,
                    'outbound_shipment_name': shipment_name
                }
            else:
                # Recupera il nome del merchant
                merchant_name = update.merchant_name
                if not merchant_name and merchant_id:
                    try:
                        logger.info(f"[_process_outbound_shipment_created] Nome merchant non disponibile, chiamata API get_merchants...")
                        start_time_merchants = time.time()
                        # COMMENTO: Disabilitata la chiamata reale all'API PrepBusiness per evitare traffico durante lo sviluppo/test.
                        # merchants_response = self.client.get_merchants()
                        # Sostituito con dati mock:
                        logger.info("[_process_outbound_shipment_created] Restituzione dati mock per get_merchants.")
                        # Simula la struttura di MerchantsResponse e Merchant
                        # class Merchant(BaseModel): id: int, name: str
                        # class MerchantsResponse(BaseModel): data: List[Merchant]
                        mock_merchant_1 = type('obj', (object,), {'id': merchant_id, 'name': f'Mock Merchant {merchant_id}'})
                        mock_merchant_2 = type('obj', (object,), {'id': 999, 'name': 'Altro Mock Merchant'})
                        merchants_response = type('obj', (object,), {'data': [mock_merchant_1, mock_merchant_2]})
                        
                        end_time_merchants = time.time()
                        logger.info(f"[_process_outbound_shipment_created] Chiamata API get_merchants (mock) completata in {end_time_merchants - start_time_merchants:.2f} secondi.")
                        merchants = merchants_response.data if merchants_response else []
                        merchant = next((m for m in merchants if str(m.id) == str(merchant_id)), None)
                        merchant_name = merchant.name if merchant else str(merchant_id)
                        logger.info(f"[_process_outbound_shipment_created] Nome merchant recuperato: {merchant_name}")
                    except Exception as e:
                        logger.error(f"[_process_outbound_shipment_created] Errore durante il recupero del nome del merchant via API: {str(e)}")
                        merchant_name = str(merchant_id)
                # Enqueue message for Chrome extension
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