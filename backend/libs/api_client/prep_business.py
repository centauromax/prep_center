"""
Client API per il servizio Prep Business.
WRAPPER DI COMPATIBILITÀ - Usa internamente il client completo libs.prepbusiness.client
"""
import requests
import logging
import json
import time
import traceback
from typing import Dict, Any, Optional, Union, List
import os

from libs.config import (
    PREP_BUSINESS_API_URL,
    PREP_BUSINESS_API_KEY,
    PREP_BUSINESS_API_TIMEOUT,
    PREP_BUSINESS_MAX_RETRIES,
    PREP_BUSINESS_RETRY_BACKOFF,
    DEFAULT_HEADERS
)

# Import del client completo
from libs.prepbusiness.client import PrepBusinessClient as CompleteClient
from libs.prepbusiness.models import PrepBusinessError, AuthenticationError

# Configura il logger
logger = logging.getLogger('prep_business')

class PrepBusinessClient:
    """
    Client wrapper per le API di Prep Business.
    
    NOTA: Questo è un wrapper di compatibilità che usa internamente
    il client completo libs.prepbusiness.client mantenendo l'interfaccia
    esistente per non rompere il codice esistente.
    """
    
    def __init__(self, api_url: str = None, api_key: str = None):
        """
        Inizializza il client API.
        
        Args:
            api_url: URL base dell'API (opzionale, default da config)
            api_key: Chiave API (opzionale, default da config)
        """
        # Prima tenta di caricare le configurazioni dal DB, se possibile
        db_config = self._get_config_from_db()
        
        # Imposta le configurazioni con priorità: parametri > db > variabili ambiente > default
        self.api_url = api_url or (db_config.get('api_url') if db_config else PREP_BUSINESS_API_URL)
        self.api_key = api_key or (db_config.get('api_key') if db_config else PREP_BUSINESS_API_KEY)
        self.timeout = int(db_config.get('api_timeout', PREP_BUSINESS_API_TIMEOUT) if db_config else PREP_BUSINESS_API_TIMEOUT)
        self.max_retries = int(db_config.get('max_retries', PREP_BUSINESS_MAX_RETRIES) if db_config else PREP_BUSINESS_MAX_RETRIES)
        self.retry_backoff = float(db_config.get('retry_backoff', PREP_BUSINESS_RETRY_BACKOFF) if db_config else PREP_BUSINESS_RETRY_BACKOFF)
        
        # Verifica che l'API key sia impostata
        if not self.api_key:
            logger.warning("API key non impostata per Prep Business API")
        
        # Estrai il company_domain dall'api_url per il client completo
        company_domain = self._extract_company_domain(self.api_url)
        
        # Inizializza il client completo internamente
        try:
            self._complete_client = CompleteClient(
                api_key=self.api_key,
                company_domain=company_domain,
                timeout=self.timeout
            )
            logger.info(f"Client completo inizializzato: Domain={company_domain}, API Key={self.api_key[:4]}..., Timeout={self.timeout}s")
        except Exception as e:
            logger.error(f"Errore inizializzazione client completo: {e}")
            self._complete_client = None
        
        # Logga le configurazioni (oscurando parte della API key per sicurezza)
        api_key_safe = self.api_key[:4] + "..." if self.api_key and len(self.api_key) > 4 else "non impostata"
        logger.info(f"Client wrapper inizializzato: URL={self.api_url}, API Key={api_key_safe}, Timeout={self.timeout}s, Retry={self.max_retries}")
    
    def _extract_company_domain(self, api_url: str) -> str:
        """
        Estrae il company_domain dall'api_url.
        
        Args:
            api_url: URL completo dell'API (es. https://dashboard.fbaprepcenteritaly.com/api)
            
        Returns:
            Company domain (es. dashboard.fbaprepcenteritaly.com)
        """
        if not api_url:
            return "dashboard.fbaprepcenteritaly.com"  # Default
            
        # Rimuovi protocollo e path
        domain = api_url.replace('https://', '').replace('http://', '')
        if '/api' in domain:
            domain = domain.split('/api')[0]
        if '/' in domain:
            domain = domain.split('/')[0]
            
        return domain
    
    def _get_config_from_db(self):
        """
        Tenta di recuperare la configurazione dal database.
        
        Returns:
            dict: Configurazione recuperata o None in caso di errore
        """
        try:
            # Import dinamico per evitare dipendenze circolari
            from django.apps import apps
            if not apps.ready:
                logger.debug("Django apps non ancora inizializzate, caricamento configurazione dal DB saltato")
                return None

            PrepBusinessConfig = apps.get_model('prep_management', 'PrepBusinessConfig')
            
            config = PrepBusinessConfig.objects.filter(is_active=True).first()
            if config:
                return {
                    'api_url': config.api_url,
                    'api_key': config.api_key,
                    'api_timeout': config.api_timeout,
                    'max_retries': config.max_retries,
                    'retry_backoff': config.retry_backoff
                }
        except (ImportError, Exception) as e:
            # Gestisce i casi in cui:
            # - Il modello non esiste
            # - Il database non è configurato
            # - La tabella non esiste ancora (migrazioni non applicate)
            logger.debug(f"Impossibile recuperare la configurazione dal database: {e}")
        
        return None
    
    def _get_headers(self, additional_headers: Dict[str, str] = None) -> Dict[str, str]:
        """
        Costruisce gli header per le richieste API.
        
        Args:
            additional_headers: Header aggiuntivi da includere
            
        Returns:
            Dict con gli header completi
        """
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        
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
        Esegue una richiesta HTTP all'API usando il client completo.
        
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
        if not self._complete_client:
            raise Exception("Client completo non inizializzato")
        
        try:
            # Usa il client completo per fare la richiesta
            if method.upper() == 'GET':
                return self._complete_client._request(
                    method=method,
                    endpoint=endpoint,
                    params=params
                )
            elif method.upper() in ['POST', 'PUT', 'PATCH']:
                return self._complete_client._request(
                    method=method,
                    endpoint=endpoint,
                    json=data,
                    params=params
                )
            else:
                return self._complete_client._request(
                    method=method,
                    endpoint=endpoint,
                    params=params
                )
        except (PrepBusinessError, AuthenticationError) as e:
            # Converte le eccezioni del client completo in RequestException per compatibilità
            raise requests.RequestException(str(e))
    
    # API wrappers per i vari endpoint - mantengono l'interfaccia esistente
    
    def get_merchants(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Ottiene la lista dei merchants configurati.
        
        Args:
            filters: Parametri di filtro opzionali
            
        Returns:
            Lista di merchants
        """
        logger.info(f"Recupero merchants con filtri: {filters}")
        
        if not self._complete_client:
            raise Exception("Client completo non inizializzato")
        
        try:
            # Usa il client completo
            response = self._complete_client.get_merchants()
            # Il client completo restituisce un oggetto MerchantsResponse, estraiamo i dati
            if hasattr(response, 'merchants'):
                merchants = [merchant.model_dump() for merchant in response.merchants]
            else:
                # Fallback se la risposta è già un dict
                merchants = response.get('data', []) if isinstance(response, dict) else []
            
            logger.info(f"Recuperati {len(merchants)} merchants")
            return merchants
        except Exception as e:
            logger.error(f"Errore recupero merchants: {e}")
            return []
    
    def get_outbound_shipment(self, shipment_id: str) -> Dict[str, Any]:
        """
        Ottiene i dettagli di una spedizione outbound.
        
        Args:
            shipment_id: ID della spedizione
            
        Returns:
            Dettagli della spedizione
        """
        if not self._complete_client:
            raise Exception("Client completo non inizializzato")
        
        try:
            response = self._complete_client.get_outbound_shipment(int(shipment_id))
            # Estrai i dati dal response object
            if hasattr(response, 'shipment'):
                return response.shipment.model_dump()
            else:
                return response.get('data', {}) if isinstance(response, dict) else {}
        except Exception as e:
            logger.error(f"Errore recupero outbound shipment {shipment_id}: {e}")
            return {}
    
    def get_inbound_shipment(self, shipment_id: str) -> Dict[str, Any]:
        """
        Ottiene i dettagli di una spedizione inbound.
        
        Args:
            shipment_id: ID della spedizione
            
        Returns:
            Dettagli della spedizione
        """
        if not self._complete_client:
            raise Exception("Client completo non inizializzato")
        
        try:
            response = self._complete_client.get_inbound_shipment(int(shipment_id))
            # Estrai i dati dal response object
            if hasattr(response, 'shipment'):
                return response.shipment.model_dump()
            else:
                return response.get('data', {}) if isinstance(response, dict) else {}
        except Exception as e:
            logger.error(f"Errore recupero inbound shipment {shipment_id}: {e}")
            return {}
    
    # Metodi specifici per inbound shipments
    
    def get_inbound_shipments(self, merchant_id: Optional[int] = None, page: int = 1, per_page: int = 50) -> List[Dict[str, Any]]:
        """
        Ottiene la lista delle spedizioni in entrata.
        
        Args:
            merchant_id: ID del merchant (opzionale)
            page: Numero di pagina
            per_page: Elementi per pagina
            
        Returns:
            Lista di spedizioni inbound
        """
        if not self._complete_client:
            raise Exception("Client completo non inizializzato")
        
        try:
            response = self._complete_client.get_inbound_shipments(
                page=page,
                per_page=per_page,
                merchant_id=merchant_id
            )
            # Estrai i dati dal response object
            if hasattr(response, 'shipments'):
                return [shipment.model_dump() for shipment in response.shipments]
            else:
                return response.get('data', []) if isinstance(response, dict) else []
        except Exception as e:
            logger.error(f"Errore recupero inbound shipments: {e}")
            return []
    
    def get_inbound_shipment_items(self, shipment_id: int, merchant_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Ottiene gli items di una spedizione inbound.
        
        Args:
            shipment_id: ID della spedizione
            merchant_id: ID del merchant (opzionale)
            
        Returns:
            Lista di items della spedizione
        """
        if not self._complete_client:
            raise Exception("Client completo non inizializzato")
        
        try:
            response = self._complete_client.get_inbound_shipment_items(
                shipment_id=shipment_id,
                merchant_id=merchant_id
            )
            # Estrai i dati dal response object
            if hasattr(response, 'items'):
                return [item.model_dump() for item in response.items]
            else:
                return response.get('data', []) if isinstance(response, dict) else []
        except Exception as e:
            logger.error(f"Errore recupero items inbound shipment {shipment_id}: {e}")
            return []
    
    # Metodi specifici per outbound shipments
    
    def get_outbound_shipments(self, merchant_id: Optional[int] = None, page: int = 1, per_page: int = 50) -> List[Dict[str, Any]]:
        """
        Ottiene la lista delle spedizioni in uscita.
        
        Args:
            merchant_id: ID del merchant (opzionale)
            page: Numero di pagina
            per_page: Elementi per pagina
            
        Returns:
            Lista di spedizioni outbound
        """
        if not self._complete_client:
            raise Exception("Client completo non inizializzato")
        
        try:
            response = self._complete_client.get_outbound_shipments(
                page=page,
                per_page=per_page,
                merchant_id=merchant_id
            )
            # Estrai i dati dal response object
            if hasattr(response, 'shipments'):
                return [shipment.model_dump() for shipment in response.shipments]
            else:
                return response.get('data', []) if isinstance(response, dict) else []
        except Exception as e:
            logger.error(f"Errore recupero outbound shipments: {e}")
            return []
    
    def get_outbound_shipment_items(self, shipment_id: int, merchant_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Ottiene gli items di una spedizione outbound.
        
        Args:
            shipment_id: ID della spedizione
            merchant_id: ID del merchant (opzionale)
            
        Returns:
            Lista di items della spedizione
        """
        if not self._complete_client:
            raise Exception("Client completo non inizializzato")
        
        try:
            response = self._complete_client.get_outbound_shipment_items(
                shipment_id=shipment_id,
                merchant_id=merchant_id
            )
            # Estrai i dati dal response object
            if hasattr(response, 'items'):
                return [item.model_dump() for item in response.items]
            else:
                return response.get('data', []) if isinstance(response, dict) else []
        except Exception as e:
            logger.error(f"Errore recupero items outbound shipment {shipment_id}: {e}")
            return []
    
    def create_inbound_shipment(self, shipment_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Crea una nuova spedizione inbound.
        
        Args:
            shipment_data: Dati della spedizione inbound
            
        Returns:
            Dettagli della spedizione creata
        """
        if not self._complete_client:
            raise Exception("Client completo non inizializzato")
        
        try:
            # Il client completo ha parametri specifici invece di un dict generico
            response = self._complete_client.create_inbound_shipment(
                name=shipment_data.get('name', ''),
                warehouse_id=shipment_data.get('warehouse_id', 1),
                notes=shipment_data.get('notes', ''),
                merchant_id=shipment_data.get('merchant_id')
            )
            # Estrai i dati dal response object
            if hasattr(response, 'shipment'):
                return response.shipment.model_dump()
            else:
                return response.get('data', {}) if isinstance(response, dict) else {}
        except Exception as e:
            logger.error(f"Errore creazione inbound shipment: {e}")
            return {}
    
    # NUOVO METODO: add_item_to_shipment (questo era il metodo mancante!)
    def add_item_to_shipment(self, shipment_id: int, item_id: int, quantity: int, merchant_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Aggiunge un item a una spedizione inbound.
        
        Args:
            shipment_id: ID della spedizione
            item_id: ID dell'item da aggiungere
            quantity: Quantità da aggiungere
            merchant_id: ID del merchant (opzionale)
            
        Returns:
            Conferma dell'aggiunta
        """
        if not self._complete_client:
            raise Exception("Client completo non inizializzato")
        
        try:
            response = self._complete_client.add_item_to_shipment(
                shipment_id=shipment_id,
                item_id=item_id,
                quantity=quantity,
                merchant_id=merchant_id
            )
            # Estrai i dati dal response object
            if hasattr(response, 'model_dump'):
                return response.model_dump()
            else:
                return response if isinstance(response, dict) else {}
        except Exception as e:
            logger.error(f"Errore aggiunta item {item_id} a shipment {shipment_id}: {e}")
            return {} 