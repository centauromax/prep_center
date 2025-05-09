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

def get_merchants(active_only: bool = True) -> List[Dict[str, Any]]:
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
        company_domain = PREP_BUSINESS_API_URL.split('//')[-1].split('/')[0]
        logger.info(f"[get_merchants] Domain estratto: {company_domain}")
        
        client = PrepBusinessClient(
            api_key=PREP_BUSINESS_API_KEY,
            company_domain=company_domain
        )
        logger.info("[get_merchants] PrepBusinessClient inizializzato correttamente")
        
        filters = {"active": True} if active_only else {}
        
        logger.info(f"[get_merchants] Esecuzione chiamata API get_merchants con filtri: {filters}")
        merchants = client.get_merchants(filters)
        
        if not hasattr(merchants, 'data'):
            logger.info(f"[get_merchants] Ricevuta risposta senza attributo 'data' dal client: {type(merchants)}")
            # Se la risposta è già una lista (vecchia versione del client)
            if isinstance(merchants, list):
                merchant_list = merchants
            else:
                logger.warning(f"[get_merchants] Tipo di risposta non riconosciuto: {type(merchants)}")
                merchant_list = []
        else:
            logger.info(f"[get_merchants] Ricevuta risposta con attributo 'data' dal client")
            merchant_list = merchants.data
        
        logger.info(f"[get_merchants] Recuperati {len(merchant_list)} merchants da Prep Business")
        
        # Converto oggetti Pydantic in dizionari se necessario
        merchant_dicts = []
        for m in merchant_list:
            if hasattr(m, 'model_dump'):
                merchant_dicts.append(m.model_dump())
            elif hasattr(m, 'dict'):
                merchant_dicts.append(m.dict())
            else:
                # Già un dizionario
                merchant_dicts.append(m)
        
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
                {'id': 1, 'name': 'Mock Merchant 1', 'active': True, 'email': 'merchant1@example.com', 'created_at': '2023-01-01T10:00:00Z'},
                {'id': 2, 'name': 'Mock Merchant 2 (Inactive)', 'active': False, 'email': 'merchant2@example.com', 'created_at': '2023-01-02T11:00:00Z'},
            ]
            if active_only:
                merchant_dicts = [m for m in merchant_dicts if m.get('active', True)]
            logger.info("[get_merchants] Restituzione dati mock per merchants come fallback.")
        
        return merchant_dicts
    except Exception as e:
        logger.error(f"[get_merchants] Errore nel recupero dei merchants: {str(e)}")
        logger.error(f"[get_merchants] Traceback: {traceback.format_exc()}")
        
        # In caso di errore, restituisci dati mock come fallback
        logger.warning("[get_merchants] Errore API, restituisco dati mock come fallback")
        merchants = [
            {'id': 1, 'name': 'Mock Merchant 1 (Fallback)', 'active': True, 'email': 'merchant1@example.com', 'created_at': '2023-01-01T10:00:00Z'},
            {'id': 2, 'name': 'Mock Merchant 2 (Inactive Fallback)', 'active': False, 'email': 'merchant2@example.com', 'created_at': '2023-01-02T11:00:00Z'},
        ]
        if active_only:
            merchants = [m for m in merchants if m.get('active', True)]
        logger.info("[get_merchants] Restituzione dati mock per merchants come fallback dopo errore.")
        return merchants 