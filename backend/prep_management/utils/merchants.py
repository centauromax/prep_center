"""
Utilities per gestire i merchants di Prep Business.
"""
import logging
from typing import List, Dict, Any, Optional

from libs.api_client.prep_business import PrepBusinessClient

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
    client = PrepBusinessClient()
    filters = {"active": True} if active_only else {}
    
    try:
        merchants = client.get_merchants(filters)
        logger.info(f"Recuperati {len(merchants)} merchants da Prep Business")
        return merchants
    except Exception as e:
        logger.error(f"Errore nel recupero dei merchants: {e}")
        return [] 