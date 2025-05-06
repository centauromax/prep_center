"""
Modulo per l'elaborazione degli eventi webhook specifici dell'applicazione.
Contiene la logica di business per reagire ai vari tipi di eventi.
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
from django.utils import timezone

from .models import ShipmentStatusUpdate, OutgoingMessage
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
        # Crea un client PrepBusiness per le chiamate API necessarie
        domain = PREP_BUSINESS_API_URL.replace('https://', '').replace('http://', '').split('/')[0]
        self.client = PrepBusinessClient(
            api_key=PREP_BUSINESS_API_KEY,
            company_domain=domain,
            timeout=PREP_BUSINESS_API_TIMEOUT,
        )
    
    def process_event(self, update_id: int) -> Dict[str, Any]:
        """
        Elabora un evento webhook in base al suo tipo.
        
        Args:
            update_id: ID dell'aggiornamento ShipmentStatusUpdate da elaborare
            
        Returns:
            Dizionario con i risultati dell'elaborazione
        """
        try:
            # Recupera l'aggiornamento dal database
            try:
                update = ShipmentStatusUpdate.objects.get(id=update_id)
            except ShipmentStatusUpdate.DoesNotExist:
                return {
                    'success': False,
                    'message': f'Aggiornamento con ID {update_id} non trovato',
                    'error': 'update_not_found'
                }
            
            # Se già elaborato, restituisce il risultato salvato
            if update.processed:
                return {
                    'success': True,
                    'message': f'Aggiornamento già elaborato in precedenza',
                    'processed': True,
                    'process_result': update.process_result or {}
                }
            
            # Elabora in base al tipo di evento
            event_type = update.event_type
            result = None
            
            if event_type == 'outbound_shipment.created':
                result = self._process_outbound_shipment_created(update)
            elif event_type.startswith('inbound_shipment.'):
                result = self._process_inbound_shipment_event(update)
            else:
                # Handler generico per eventi non specificamente gestiti
                result = {
                    'success': True,
                    'message': f'Evento {event_type} ricevuto ma nessuna elaborazione specifica richiesta',
                }
            
            # Aggiorna il record con il risultato dell'elaborazione
            update.processed = True
            update.processed_at = timezone.now()
            update.process_success = result.get('success', False)
            update.process_message = result.get('message', '')
            update.process_result = result
            update.save()
            
            return result
            
        except Exception as e:
            logger.error(f"Errore durante l'elaborazione dell'evento: {str(e)}")
            logger.exception("Traceback completo:")
            
            # Aggiorna il record con l'errore
            try:
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
            except Exception:
                # In caso di errore anche nel salvataggio, logga e continua
                logger.exception("Errore durante il salvataggio dell'errore di elaborazione")
            
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
            # Ottieni tutte le spedizioni in entrata per questo merchant
            inbound_shipments_response = self.client.get_inbound_shipments(merchant_id=merchant_id)
            inbound_shipments = inbound_shipments_response.data
            # Filtra solo le spedizioni in entrata non archiviate
            inbound_shipments = [s for s in inbound_shipments if s.archived_at is None]
            
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
                        merchants = self.client.get_merchants().data
                        merchant = next((m for m in merchants if str(m.id) == str(merchant_id)), None)
                        merchant_name = merchant.name if merchant else str(merchant_id)
                    except Exception as e:
                        merchant_name = str(merchant_id)
                # Enqueue message for Chrome extension
                OutgoingMessage.objects.create(
                    message_id='OUTBOUND_WITHOUT_INBOUND',
                    parameters={
                        'merchant_name': merchant_name,
                        'outbound_shipment_name': shipment_name
                    }
                )
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