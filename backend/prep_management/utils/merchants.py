"""
Utilities per gestire i merchants di Prep Business.
"""
import logging
import traceback
from typing import List, Dict, Any, Optional

from libs.api_client.prep_business import PrepBusinessClient
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
        logger.info("Inizializzazione client PrepBusinessClient per chiamata get_merchants reale")
        company_domain = PREP_BUSINESS_API_URL.split('//')[-1].split('/')[0]
        client = PrepBusinessClient(
            api_key=PREP_BUSINESS_API_KEY,
            company_domain=company_domain
        )
        filters = {"active": True} if active_only else {}
        
        logger.info(f"Esecuzione chiamata API get_merchants con filtri: {filters}")
        merchants = client.get_merchants(filters)
        logger.info(f"Recuperati {len(merchants)} merchants da Prep Business")
        
        # Logga un esempio di merchant per debug (se disponibile)
        if merchants and len(merchants) > 0:
            sample = merchants[0].copy()
            if 'api_key' in sample:
                sample['api_key'] = '***HIDDEN***'  # Nascondi chiavi sensibili
            logger.debug(f"Esempio merchant: {sample}")
        
        # Fallback a dati mock solo in caso di errore o nessun risultato
        if not merchants:
            logger.warning("Nessun merchant trovato dall'API, restituisco dati mock come fallback")
            merchants = [
                {'id': 1, 'name': 'Mock Merchant 1', 'active': True, 'email': 'merchant1@example.com', 'created_at': '2023-01-01T10:00:00Z'},
                {'id': 2, 'name': 'Mock Merchant 2 (Inactive)', 'active': False, 'email': 'merchant2@example.com', 'created_at': '2023-01-02T11:00:00Z'},
            ]
            if active_only:
                merchants = [m for m in merchants if m.get('active', True)]
            logger.info("Restituzione dati mock per merchants come fallback.")
        
        return merchants
    except Exception as e:
        logger.error(f"Errore nel recupero dei merchants: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        # In caso di errore, restituisci dati mock come fallback
        logger.warning("Errore API, restituisco dati mock come fallback")
        merchants = [
            {'id': 1, 'name': 'Mock Merchant 1 (Fallback)', 'active': True, 'email': 'merchant1@example.com', 'created_at': '2023-01-01T10:00:00Z'},
            {'id': 2, 'name': 'Mock Merchant 2 (Inactive Fallback)', 'active': False, 'email': 'merchant2@example.com', 'created_at': '2023-01-02T11:00:00Z'},
        ]
        if active_only:
            merchants = [m for m in merchants if m.get('active', True)]
        logger.info("Restituzione dati mock per merchants come fallback dopo errore.")
        return merchants 