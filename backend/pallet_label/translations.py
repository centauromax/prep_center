"""
Traduzioni per le etichette pallet in diverse lingue
"""

TRANSLATIONS = {
    'it': {
        'vendor': 'Venditore',
        'shipment_name': 'Nome spedizione',
        'shipment_number': 'Numero spedizione',
        'origin_address': 'Origine spedizione',
        'destination_address': 'Indirizzo di spedizione',
        'box_count': 'Numero di cartoni',
        'pallet_label': 'Pallet n. {pallet_num} di {total_pallets}'
    },
    'fr': {
        'vendor': 'Vendeur',
        'shipment_name': 'Nom de l\'expédition',
        'shipment_number': 'Numéro d\'expédition',
        'origin_address': 'Origine de l\'expédition',
        'destination_address': 'Adresse de livraison',
        'box_count': 'Nombre de cartons',
        'pallet_label': 'Palette n° {pallet_num} de {total_pallets}'
    },
    'de': {
        'vendor': 'Verkäufer',
        'shipment_name': 'Sendungsname',
        'shipment_number': 'Sendungsnummer',
        'origin_address': 'Ursprungsadresse',
        'destination_address': 'Lieferadresse',
        'box_count': 'Anzahl der Kartons',
        'pallet_label': 'Palette Nr. {pallet_num} von {total_pallets}'
    },
    'es': {
        'vendor': 'Vendedor',
        'shipment_name': 'Nombre del envío',
        'shipment_number': 'Número de envío',
        'origin_address': 'Origen del envío',
        'destination_address': 'Dirección de envío',
        'box_count': 'Número de cajas',
        'pallet_label': 'Palet n.º {pallet_num} de {total_pallets}'
    }
}

def get_translation(language_code, key, **kwargs):
    """
    Ottiene la traduzione per una chiave specifica in una lingua
    
    Args:
        language_code: Codice lingua (it, fr, de, es)
        key: Chiave della traduzione
        **kwargs: Parametri per il formatting
        
    Returns:
        str: Testo tradotto
    """
    translations = TRANSLATIONS.get(language_code, TRANSLATIONS['it'])
    text = translations.get(key, TRANSLATIONS['it'][key])
    
    if kwargs:
        return text.format(**kwargs)
    return text 