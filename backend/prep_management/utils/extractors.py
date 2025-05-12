from typing import Any, Dict
import logging

logger = logging.getLogger('prep_management')

def extract_product_info_from_dict(item_dict: Dict[str, Any], shipment_type: str) -> Dict[str, Any]:
    """Estrae SKU, ASIN, FNSKU, Titolo e Quantità da un item_dict."""
    logger.debug(f"[EXTRACTOR] Estrattore chiamato con shipment_type={shipment_type}, item={str(item_dict)[:200]}...")
    
    product_title = None
    product_sku = None
    product_asin = None
    product_fnsku = None
    product_quantity = item_dict.get('quantity', 0)

    if shipment_type == 'inbound':
        product_title = item_dict.get('name')
        product_sku = item_dict.get('sku')
        product_asin = item_dict.get('asin')
        logger.debug(f"[EXTRACTOR] Modalità inbound: title={product_title}, sku={product_sku}, asin={product_asin}")
    elif shipment_type == 'outbound':
        inventory_item_data = item_dict.get('item') if isinstance(item_dict, dict) else None
        logger.debug(f"[EXTRACTOR] Modalità outbound: item_dict ha chiave 'item'? {inventory_item_data is not None}")
        
        if inventory_item_data and isinstance(inventory_item_data, dict):
            product_title = inventory_item_data.get('title')
            product_sku = inventory_item_data.get('merchant_sku')
            product_asin = inventory_item_data.get('asin')
            product_fnsku = inventory_item_data.get('fnsku')
            logger.debug(f"[EXTRACTOR] Dati da inventory_item: title={product_title}, sku={product_sku}, asin={product_asin}, fnsku={product_fnsku}")
            
            if not product_asin and 'identifiers' in inventory_item_data:
                for ident in inventory_item_data.get('identifiers', []):
                    if ident.get('identifier_type') == 'ASIN':
                        product_asin = ident.get('identifier')
                        logger.debug(f"[EXTRACTOR] ASIN trovato in identifiers: {product_asin}")
                        break
            
            if not product_fnsku and 'identifiers' in inventory_item_data:
                for ident in inventory_item_data.get('identifiers', []):
                    if ident.get('identifier_type') == 'FNSKU':
                        product_fnsku = ident.get('identifier')
                        logger.debug(f"[EXTRACTOR] FNSKU trovato in identifiers: {product_fnsku}")
                        break
    
    result = {
        'title': product_title or f"Prodotto senza titolo (ID: {item_dict.get('id', 'N/A')})",
        'sku': product_sku or "N/A",
        'asin': product_asin or "N/A",
        'fnsku': product_fnsku or "N/A",
        'quantity': product_quantity or 0
    }
    
    # Se almeno il titolo è presente, considera il risultato valido
    is_valid = product_title is not None and product_title != ""
    logger.debug(f"[EXTRACTOR] Risultato valido: {is_valid}, title={result['title']}")
    
    return result if is_valid else None 