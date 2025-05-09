# COMMENTO: Disabilitata la chiamata reale all'API PrepBusiness per evitare traffico durante lo sviluppo/test.
# shipments_response = prep_client.get_inbound_shipments(...)
# Sostituito con dati mock:
shipments_response = type('obj', (object,), {'data': [
    {'id': 1, 'merchant': 'TestMerchant', 'type': 'inbound', 'status': 'open', 'created_at': '2024-06-01'},
    {'id': 2, 'merchant': 'TestMerchant', 'type': 'outbound', 'status': 'closed', 'created_at': '2024-06-02'},
]})()

# COMMENTO: Disabilitata la chiamata reale all'API PrepBusiness per evitare traffico durante lo sviluppo/test.
# shipment_details = prep_client.get_inbound_shipment_details(...)
# Sostituito con dati mock:
shipment_details = {'id': 1, 'merchant': 'TestMerchant', 'type': 'inbound', 'status': 'open', 'created_at': '2024-06-01'}

# COMMENTO: Disabilitata la chiamata reale all'API PrepBusiness per evitare traffico durante lo sviluppo/test.
# items_response = prep_client.get_inbound_shipment_items(...)
# Sostituito con dati mock:
items_response = type('obj', (object,), {'data': [
    {'product_name': 'Prodotto di esempio', 'quantity': 10},
]})() 