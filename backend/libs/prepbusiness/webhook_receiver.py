"""
Modulo per la ricezione e gestione dei webhook da PrepBusiness.
Fornisce un'interfaccia unificata per verificare, elaborare e salvare le notifiche ricevute.
"""

import json
import hmac
import hashlib
import logging
import time
from typing import Optional, Dict, Any, Union, Tuple, Callable
from django.http import HttpRequest, HttpResponse

from .webhook_processor import WebhookProcessor

logger = logging.getLogger('prep_management')

class WebhookReceiver:
    """
    Classe per ricevere, verificare e processare i webhook da PrepBusiness.
    
    Questa classe fornisce metodi per:
    - Verificare la firma dei webhook
    - Elaborare i dati ricevuti
    - Rispondere alle richieste webhook
    - Delegare il salvataggio dei dati al chiamante
    """
    
    def __init__(self, webhook_secret: Optional[str] = None):
        """
        Inizializza il ricevitore webhook.
        
        Args:
            webhook_secret: Chiave segreta per verificare le firme webhook
        """
        self.webhook_secret = webhook_secret
    
    def verify_signature(self, payload: Union[str, bytes], signature: str) -> bool:
        """
        Verifica la firma HMAC-SHA256 del payload del webhook.
        
        Args:
            payload: Il payload raw della richiesta
            signature: La firma fornita nell'header
            
        Returns:
            bool: True se la firma è valida o nessuna secret key è configurata, False altrimenti
        """
        if not self.webhook_secret or not signature:
            # Se non c'è una secret key o una firma, non possiamo verificare
            # In produzione, si dovrebbe restituire False se configurato per richiedere la verifica
            return True
        
        # Assicurati che il payload sia in bytes
        if isinstance(payload, str):
            payload = payload.encode('utf-8')
        
        # Calcola l'HMAC del payload
        computed_signature = hmac.new(
            self.webhook_secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        # Confronta la firma calcolata con quella fornita
        return hmac.compare_digest(computed_signature, signature)
    
    def process_webhook(
        self, 
        request: HttpRequest, 
        save_callback: Optional[Callable[[Dict[str, Any]], Any]] = None
    ) -> Tuple[HttpResponse, Dict[str, Any]]:
        """
        Processa una richiesta webhook da PrepBusiness.
        
        Args:
            request: La richiesta HTTP contenente il webhook
            save_callback: Funzione opzionale per salvare i dati elaborati
            
        Returns:
            Tuple con la risposta HTTP e i dati elaborati (o None in caso di errore)
        """
        debug_timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        method = request.method
        headers = dict(request.headers)
        
        # Log delle informazioni di debug
        logger.info(f"[DEBUG {debug_timestamp}] Richiesta webhook ricevuta via {method}")
        logger.info(f"[DEBUG {debug_timestamp}] Headers: {headers}")
        
        # Gestisci richieste GET come verifica dell'endpoint
        if method == 'GET':
            response = HttpResponse(
                json.dumps({
                    'status': 'ok',
                    'message': 'Webhook endpoint is accessible, but only POST requests are processed',
                    'timestamp': debug_timestamp,
                    'method': method
                }),
                content_type='application/json'
            )
            return response, None
        
        # Log del payload per richieste POST
        body = request.body
        if hasattr(body, 'decode'):
            body_text = body.decode('utf-8', errors='replace')
            logger.info(f"[DEBUG {debug_timestamp}] Body: {body_text}")
        
        try:
            # Verifica la firma del webhook se impostata una secret key
            if self.webhook_secret:
                signature = request.headers.get('X-Webhook-Signature') or request.headers.get('Signature')
                if not self.verify_signature(body, signature):
                    logger.warning(f"[DEBUG {debug_timestamp}] Firma webhook non valida")
                    return HttpResponse("Firma non valida", status=403), None
            
            try:
                # Utilizza il processore webhook per interpretare e normalizzare i dati
                webhook_data = WebhookProcessor.parse_payload(body)
                logger.info(f"[DEBUG {debug_timestamp}] Webhook elaborato: {webhook_data}")
                
                # Verifica che l'ID entità sia stato estratto
                if not webhook_data.get('shipment_id'):
                    logger.error(f"[DEBUG {debug_timestamp}] Dati webhook incompleti - nessun ID entità trovato")
                    return HttpResponse("Dati incompleti - ID entità mancante", status=400), None
                
                # Salva i dati se viene fornita una funzione di callback
                saved_data = None
                if save_callback:
                    saved_data = save_callback(webhook_data)
                    
                logger.info(
                    f"[DEBUG {debug_timestamp}] Aggiornamento entità {webhook_data.get('shipment_id')} ricevuto: "
                    f"{webhook_data.get('event_type')} - {webhook_data.get('previous_status')} → "
                    f"{webhook_data.get('new_status')}"
                )
                
                return HttpResponse("OK", status=200), webhook_data
                
            except json.JSONDecodeError:
                logger.error(f"[DEBUG {debug_timestamp}] Payload webhook non è un JSON valido: {body}")
                return HttpResponse("Payload non valido", status=400), None
            except ValueError as e:
                logger.error(f"[DEBUG {debug_timestamp}] Errore durante l'elaborazione del payload: {str(e)}")
                return HttpResponse(f"Errore di elaborazione: {str(e)}", status=400), None
            
        except Exception as e:
            logger.error(f"[DEBUG {debug_timestamp}] Errore durante l'elaborazione del webhook: {str(e)}")
            logger.exception("Traceback completo:")
            return HttpResponse("Errore interno", status=500), None 