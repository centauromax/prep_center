from typing import Any, Dict

def extract_product_info_from_dict(item_dict: Dict[str, Any], shipment_type: str) -> Dict[str, Any]:
    """Estrae SKU, ASIN, FNSKU, Titolo e Quantità da un item_dict."""
    product_title = None
    product_sku = None
    product_asin = None
    product_fnsku = None
    product_quantity = item_dict.get('quantity')

    if shipment_type == 'inbound':
        product_title = item_dict.get('name')
        product_sku = item_dict.get('sku')
        product_asin = item_dict.get('asin')
    elif shipment_type == 'outbound':
        inventory_item_data = item_dict.get('item') if isinstance(item_dict, dict) else None
        if inventory_item_data and isinstance(inventory_item_data, dict):
            product_title = inventory_item_data.get('title')
            product_sku = inventory_item_data.get('merchant_sku')
            product_asin = inventory_item_data.get('asin')
            product_fnsku = inventory_item_data.get('fnsku')
            if not product_asin and 'identifiers' in inventory_item_data:
                for ident in inventory_item_data.get('identifiers', []):
                    if ident.get('identifier_type') == 'ASIN':
                        product_asin = ident.get('identifier')
                        break
            if not product_fnsku and 'identifiers' in inventory_item_data:
                for ident in inventory_item_data.get('identifiers', []):
                    if ident.get('identifier_type') == 'FNSKU':
                        product_fnsku = ident.get('identifier')
                        break
    return {
        'title': product_title,
        'sku': product_sku,
        'asin': product_asin,
        'fnsku': product_fnsku,
        'quantity': product_quantity
    } 