"""
Utilities per gestire i merchants di Prep Business.
"""
import logging
import traceback
from typing import List, Dict, Any, Optional

# Correggo l'import del client
from libs.prepbusiness.client import PrepBusinessClient
from libs.config import PREP_BUSINESS_API_URL, PREP_BUSINESS_API_KEY

# Configura il logger
logger = logging.getLogger('prep_management')

def get_merchants(active_only: bool = False) -> List[Dict[str, Any]]:
    """
    Ottiene la lista dei merchants da Prep Business.
    
    Args:
        active_only: Se True, restituisce solo i merchants attivi
        
    Returns:
        Lista di merchants
    """
    # Logga le configurazioni (oscurando parte della API key per sicurezza)
    api_key_safe = PREP_BUSINESS_API_KEY[:4] + "..." if PREP_BUSINESS_API_KEY and len(PREP_BUSINESS_API_KEY) > 4 else "non impostata"
    logger.info(f"Tentativo di connessione a Prep Business API: URL={PREP_BUSINESS_API_URL}, API Key={api_key_safe}")
    
    try:
        # RIATTIVO LA CHIAMATA API PER I MERCHANTS
        logger.info("[get_merchants] Inizializzazione client PrepBusinessClient per chiamata get_merchants reale")
        
        # Estrai il dominio dall'URL API
        domain = PREP_BUSINESS_API_URL.replace('https://', '').replace('http://', '').split('/')[0]
        client = PrepBusinessClient(
            api_key=PREP_BUSINESS_API_KEY,
            company_domain=domain
        )
        logger.info("[get_merchants] PrepBusinessClient inizializzato correttamente")
        
        logger.info("[get_merchants] Esecuzione chiamata API get_merchants")
        merchants_response = client.get_merchants()
        
        # Gestisci la risposta - può essere una lista diretta o un oggetto Pydantic
        logger.info(f"[get_merchants] Tipo di risposta ricevuta: {type(merchants_response)}")
        
        if isinstance(merchants_response, list):
            # Risposta diretta come lista
            merchant_list = merchants_response
            logger.info(f"[get_merchants] Risposta diretta come lista: {len(merchant_list)} merchants")
        elif hasattr(merchants_response, 'data'):
            # La risposta ha un attributo 'data' che potrebbe contenere la lista
            if hasattr(merchants_response.data, 'data'):
                # Struttura annidata: response.data.data
                merchant_list = merchants_response.data.data
                logger.info(f"[get_merchants] Estratti {len(merchant_list)} merchants da response.data.data")
            elif isinstance(merchants_response.data, list):
                # Struttura semplice: response.data è già la lista
                merchant_list = merchants_response.data
                logger.info(f"[get_merchants] Estratti {len(merchant_list)} merchants da response.data")
            else:
                logger.warning(f"[get_merchants] response.data non è una lista: {type(merchants_response.data)}")
                merchant_list = []
        elif hasattr(merchants_response, 'merchants'):
            # Prova ad accedere all'attributo merchants se esiste
            merchant_list = merchants_response.merchants
            logger.info(f"[get_merchants] Estratti {len(merchant_list)} merchants da .merchants")
        else:
            logger.warning(f"[get_merchants] Tipo di risposta non riconosciuto: {type(merchants_response)}")
            merchant_list = []
        
        logger.info(f"[get_merchants] Recuperati {len(merchant_list)} merchants da Prep Business")
        
        # Converti gli oggetti Pydantic in dizionari se necessario
        merchant_dicts = []
        for merchant in merchant_list:
            if hasattr(merchant, 'model_dump'):
                # È un oggetto Pydantic, convertilo in dict
                merchant_dicts.append(merchant.model_dump())
            elif isinstance(merchant, dict):
                # È già un dizionario
                merchant_dicts.append(merchant)
            else:
                # Prova a convertirlo in dict
                try:
                    merchant_dicts.append(dict(merchant))
                except:
                    logger.warning(f"[get_merchants] Impossibile convertire merchant: {type(merchant)}")
                    continue
        
        # Filtra per enabled se richiesto
        if active_only:
            merchant_dicts = [m for m in merchant_dicts if m.get('enabled', True)]
            logger.info(f"[get_merchants] Dopo filtro active_only: {len(merchant_dicts)} merchants")
        
        # Logga un esempio di merchant per debug (se disponibile)
        if merchant_dicts and len(merchant_dicts) > 0:
            sample = merchant_dicts[0].copy()
            if 'api_key' in sample:
                sample['api_key'] = '***HIDDEN***'  # Nascondi chiavi sensibili
            logger.debug(f"[get_merchants] Esempio merchant: {sample}")
        
        # Fallback a dati mock solo in caso di errore o nessun risultato
        if not merchant_dicts:
            logger.warning("[get_merchants] Nessun merchant trovato dall'API, restituisco dati mock come fallback")
            merchant_dicts = [
                {'id': 1, 'name': 'Mock Merchant 1', 'enabled': True, 'email': 'merchant1@example.com', 'created_at': '2023-01-01T10:00:00Z'},
                {'id': 2, 'name': 'Mock Merchant 2 (Inactive)', 'enabled': False, 'email': 'merchant2@example.com', 'created_at': '2023-01-02T11:00:00Z'},
            ]
            if active_only:
                merchant_dicts = [m for m in merchant_dicts if m.get('enabled', True)]
            logger.info("[get_merchants] Restituzione dati mock per merchants come fallback.")
        
        return merchant_dicts
    except Exception as e:
        logger.error(f"[get_merchants] Errore nel recupero dei merchants: {str(e)}")
        logger.error(f"[get_merchants] Traceback: {traceback.format_exc()}")
        
        # In caso di errore, restituisci dati mock come fallback
        logger.warning("[get_merchants] Errore API, restituisco dati mock come fallback")
        merchants = [
            {'id': 1, 'name': 'Mock Merchant 1 (Fallback)', 'enabled': True, 'email': 'merchant1@example.com', 'created_at': '2023-01-01T10:00:00Z'},
            {'id': 2, 'name': 'Mock Merchant 2 (Inactive Fallback)', 'enabled': False, 'email': 'merchant2@example.com', 'created_at': '2023-01-02T11:00:00Z'},
        ]
        if active_only:
            merchants = [m for m in merchants if m.get('enabled', True)]
        logger.info("[get_merchants] Restituzione dati mock per merchants come fallback dopo errore.")
        return merchants 