"""
Client API per il servizio Prep Business.
"""
import requests
import logging
import json
import time
import traceback
from typing import Dict, Any, Optional, Union, List

from libs.config import (
    PREP_BUSINESS_API_URL,
    PREP_BUSINESS_API_KEY,
    PREP_BUSINESS_API_TIMEOUT,
    PREP_BUSINESS_MAX_RETRIES,
    PREP_BUSINESS_RETRY_BACKOFF,
    DEFAULT_HEADERS
)

# Configura il logger
logger = logging.getLogger('prep_business')

class PrepBusinessClient:
    """Client per le API di Prep Business."""
    
    def __init__(self, api_url: str = None, api_key: str = None):
        """
        Inizializza il client API.
        
        Args:
            api_url: URL base dell'API (opzionale, default da config)
            api_key: Chiave API (opzionale, default da config)
        """
        self.api_url = api_url or PREP_BUSINESS_API_URL
        self.api_key = api_key or PREP_BUSINESS_API_KEY
        self.timeout = PREP_BUSINESS_API_TIMEOUT
        self.max_retries = PREP_BUSINESS_MAX_RETRIES
        self.retry_backoff = PREP_BUSINESS_RETRY_BACKOFF
        
        # Verifica che l'API key sia impostata
        if not self.api_key:
            logger.warning("API key non impostata per Prep Business API")
        
        # Logga le configurazioni (oscurando parte della API key per sicurezza)
        api_key_safe = self.api_key[:4] + "..." if self.api_key and len(self.api_key) > 4 else "non impostata"
        logger.info(f"Client API inizializzato: URL={self.api_url}, API Key={api_key_safe}, Timeout={self.timeout}s, Retry={self.max_retries}")
    
    def _get_headers(self, additional_headers: Dict[str, str] = None) -> Dict[str, str]:
        """
        Costruisce gli header per le richieste API.
        
        Args:
            additional_headers: Header aggiuntivi da includere
            
        Returns:
            Dict con gli header completi
        """
        headers = DEFAULT_HEADERS.copy()
        headers['Authorization'] = f'Bearer {self.api_key}'
        
        if additional_headers:
            headers.update(additional_headers)
            
        return headers
    
    def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Esegue una richiesta HTTP all'API con retry in caso di errore.
        
        Args:
            method: Metodo HTTP ('GET', 'POST', ecc.)
            endpoint: Endpoint API (senza l'URL base)
            data: Dati da inviare (per POST, PUT, ecc.)
            params: Parametri query string
            headers: Header aggiuntivi
            
        Returns:
            Dict con la risposta JSON dell'API
            
        Raises:
            requests.RequestException: Se la richiesta fallisce dopo tutti i retry
        """
        url = f"{self.api_url}/{endpoint.lstrip('/')}"
        all_headers = self._get_headers(headers)
        
        # Rimuovi Authorization per il logging
        log_headers = all_headers.copy()
        if 'Authorization' in log_headers:
            log_headers['Authorization'] = 'Bearer ***HIDDEN***'
        
        logger.info(f"Esecuzione richiesta {method} a {url}")
        logger.debug(f"Headers: {log_headers}")
        logger.debug(f"Params: {params}")
        if data and method.upper() in ['POST', 'PUT', 'PATCH']:
            logger.debug(f"Data: {json.dumps(data)[:200]}...")
        
        retry_count = 0
        last_exception = None
        
        while retry_count <= self.max_retries:
            try:
                logger.debug(f"Richiesta {method} a {url} (tentativo {retry_count+1}/{self.max_retries+1})")
                
                response = requests.request(
                    method=method,
                    url=url,
                    json=data if method.upper() in ['POST', 'PUT', 'PATCH'] else None,
                    params=params,
                    headers=all_headers,
                    timeout=self.timeout
                )
                
                # Log della risposta
                logger.debug(f"Risposta status code: {response.status_code}")
                logger.debug(f"Risposta headers: {response.headers}")
                
                # Verifica se la risposta è valida
                try:
                    response.raise_for_status()
                except requests.exceptions.HTTPError as e:
                    logger.error(f"Errore HTTP: {e}")
                    logger.error(f"Risposta: {response.text[:500]}")
                    raise
                
                try:
                    result = response.json()
                    logger.debug(f"Risposta JSON: {json.dumps(result)[:500]}...")
                    return result
                except json.JSONDecodeError:
                    logger.warning(f"Risposta non JSON: {response.text[:500]}")
                    return {"text": response.text}
                    
            except requests.exceptions.RequestException as e:
                last_exception = e
                retry_count += 1
                
                if retry_count <= self.max_retries:
                    # Calcola il tempo di attesa con backoff esponenziale
                    wait_time = self.retry_backoff * (2 ** (retry_count - 1))
                    logger.warning(f"Errore nella richiesta API: {e}. Retry in {wait_time:.2f} secondi...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Fallimento dopo {self.max_retries} tentativi: {e}")
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    raise
        
        if last_exception:
            raise last_exception
        
        return {}  # Non dovrebbe mai arrivare qui
    
    # API wrappers per i vari endpoint
    
    def get_merchants(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Ottiene la lista dei merchants configurati.
        
        Args:
            filters: Parametri di filtro opzionali
            
        Returns:
            Lista di merchants
        """
        logger.info(f"Recupero merchants con filtri: {filters}")
        response = self._make_request('GET', '/merchants', params=filters)
        merchants = response.get('data', [])
        logger.info(f"Recuperati {len(merchants)} merchants")
        return merchants
    
    def get_shipments(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Ottiene la lista delle spedizioni.
        
        Args:
            filters: Parametri di filtro opzionali
            
        Returns:
            Lista di spedizioni
        """
        response = self._make_request('GET', '/shipments', params=filters)
        return response.get('data', [])
    
    def get_shipment(self, shipment_id: str) -> Dict[str, Any]:
        """
        Ottiene i dettagli di una spedizione.
        
        Args:
            shipment_id: ID della spedizione
            
        Returns:
            Dettagli della spedizione
        """
        response = self._make_request('GET', f'/shipments/{shipment_id}')
        return response.get('data', {})
    
    def create_shipment(self, shipment_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Crea una nuova spedizione.
        
        Args:
            shipment_data: Dati della spedizione
            
        Returns:
            Dettagli della spedizione creata
        """
        response = self._make_request('POST', '/shipments', data=shipment_data)
        return response.get('data', {})
    
    def update_shipment(self, shipment_id: str, shipment_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Aggiorna una spedizione esistente.
        
        Args:
            shipment_id: ID della spedizione
            shipment_data: Dati aggiornati della spedizione
            
        Returns:
            Dettagli della spedizione aggiornata
        """
        response = self._make_request('PUT', f'/shipments/{shipment_id}', data=shipment_data)
        return response.get('data', {}) 