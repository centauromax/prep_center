"""
Utilità per la gestione dei messaggi bidirezionali tra app e estensione browser.
"""

import uuid
import logging
import time
from typing import Optional, Dict, Any, List
from django.utils import timezone
from ..models import OutgoingMessage, IncomingMessage

logger = logging.getLogger('prep_management')


class MessageSession:
    """
    Classe per gestire una sessione di comunicazione bidirezionale con l'estensione.
    """
    
    def __init__(self, session_id: Optional[str] = None):
        """
        Inizializza una sessione di messaggistica.
        
        Args:
            session_id: ID della sessione. Se None, ne viene generato uno nuovo.
        """
        self.session_id = session_id or str(uuid.uuid4())
        logger.info(f"Inizializzata sessione messaggi: {self.session_id}")
    
    def send_to_extension(self, message_type: str, parameters: Dict[str, Any]) -> OutgoingMessage:
        """
        Invia un messaggio all'estensione.
        
        Args:
            message_type: Tipo di messaggio (OUTBOUND_WITHOUT_INBOUND, BOX_SERVICES_REQUEST)
            parameters: Parametri del messaggio
            
        Returns:
            L'oggetto OutgoingMessage creato
        """
        # Aggiungi session_id ai parametri
        parameters['session_id'] = self.session_id
        
        msg = OutgoingMessage.objects.create(
            message_id=message_type,
            parameters=parameters
        )
        
        logger.info(f"Messaggio inviato all'estensione: {message_type} (session: {self.session_id})")
        return msg
    
    def wait_for_response(self, 
                         timeout: int = 30, 
                         expected_message_type: Optional[str] = None) -> List[IncomingMessage]:
        """
        Attende una risposta dall'estensione per questa sessione.
        
        Args:
            timeout: Timeout in secondi
            expected_message_type: Tipo di messaggio atteso (opzionale)
            
        Returns:
            Lista dei messaggi ricevuti
        """
        logger.info(f"Attendo risposta per sessione {self.session_id} (timeout: {timeout}s)")
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # Cerca messaggi per questa sessione
            query = IncomingMessage.objects.filter(session_id=self.session_id, processed=False)
            
            if expected_message_type:
                query = query.filter(message_type=expected_message_type)
            
            messages = list(query.order_by('created_at'))
            
            if messages:
                # Marca i messaggi come processati
                message_ids = [msg.id for msg in messages]
                IncomingMessage.objects.filter(id__in=message_ids).update(
                    processed=True,
                    processed_at=timezone.now()
                )
                
                logger.info(f"Ricevuti {len(messages)} messaggi per sessione {self.session_id}")
                return messages
            
            # Attendi un po' prima del prossimo controllo
            time.sleep(0.5)
        
        # Timeout raggiunto
        logger.warning(f"Timeout raggiunto per sessione {self.session_id}")
        return []
    
    def send_and_wait(self, 
                     message_type: str, 
                     parameters: Dict[str, Any],
                     timeout: int = 30,
                     expected_response_type: Optional[str] = None) -> tuple[OutgoingMessage, List[IncomingMessage]]:
        """
        Invia un messaggio e attende una risposta.
        
        Args:
            message_type: Tipo di messaggio da inviare
            parameters: Parametri del messaggio
            timeout: Timeout per l'attesa della risposta
            expected_response_type: Tipo di risposta atteso
            
        Returns:
            Tupla con (messaggio_inviato, messaggi_ricevuti)
        """
        sent_msg = self.send_to_extension(message_type, parameters)
        received_msgs = self.wait_for_response(timeout, expected_response_type)
        
        return sent_msg, received_msgs


def send_outbound_without_inbound_notification(merchant_name: str, 
                                             outbound_shipment_name: str,
                                             wait_for_response: bool = False,
                                             timeout: int = 30) -> tuple[OutgoingMessage, List[IncomingMessage]]:
    """
    Invia una notifica di spedizione outbound senza inbound corrispondente.
    
    Args:
        merchant_name: Nome del merchant
        outbound_shipment_name: Nome della spedizione outbound
        wait_for_response: Se attendere una risposta dall'utente
        timeout: Timeout per l'attesa della risposta
        
    Returns:
        Tupla con (messaggio_inviato, messaggi_ricevuti)
    """
    session = MessageSession()
    
    parameters = {
        'merchant_name': merchant_name,
        'outbound_shipment_name': outbound_shipment_name
    }
    
    if wait_for_response:
        return session.send_and_wait(
            'OUTBOUND_WITHOUT_INBOUND', 
            parameters, 
            timeout, 
            'USER_RESPONSE'
        )
    else:
        sent_msg = session.send_to_extension('OUTBOUND_WITHOUT_INBOUND', parameters)
        return sent_msg, []


def send_box_services_request(payload: Dict[str, Any],
                            wait_for_response: bool = False,
                            timeout: int = 30) -> tuple[OutgoingMessage, List[IncomingMessage]]:
    """
    Invia una richiesta di servizi box.
    
    Args:
        payload: Payload della richiesta
        wait_for_response: Se attendere una risposta dall'utente
        timeout: Timeout per l'attesa della risposta
        
    Returns:
        Tupla con (messaggio_inviato, messaggi_ricevuti)
    """
    session = MessageSession()
    
    if wait_for_response:
        return session.send_and_wait(
            'BOX_SERVICES_REQUEST', 
            payload, 
            timeout, 
            'ACTION_COMPLETED'
        )
    else:
        sent_msg = session.send_to_extension('BOX_SERVICES_REQUEST', payload)
        return sent_msg, []


def cleanup_old_messages(hours: int = 24):
    """
    Pulisce i messaggi vecchi dal database.
    
    Args:
        hours: Ore di anzianità oltre le quali eliminare i messaggi
    """
    from datetime import timedelta
    cutoff_time = timezone.now() - timedelta(hours=hours)
    
    # Elimina messaggi in uscita consumati vecchi
    deleted_outgoing = OutgoingMessage.objects.filter(
        consumed=True, 
        consumed_at__lt=cutoff_time
    ).delete()
    
    # Elimina messaggi in entrata processati vecchi
    deleted_incoming = IncomingMessage.objects.filter(
        processed=True, 
        processed_at__lt=cutoff_time
    ).delete()
    
    logger.info(f"Cleanup messaggi: eliminati {deleted_outgoing[0]} outgoing e {deleted_incoming[0]} incoming")
    
    return deleted_outgoing[0] + deleted_incoming[0] 