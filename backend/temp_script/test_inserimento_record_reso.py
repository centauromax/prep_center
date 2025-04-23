from return_management.models import ProductReturn  # Importa il modello corretto

# Ora prova a eseguire l'inserimento di test
ProductReturn.objects.create(
    box=123,
    box_type="Test Box",
    picked=None,
    shipped=None,
    lpn="TESTLPN123",
    brand="Test Brand",
    product_description="Test Description",
    additional_info=None,
    other_info=None,
    destination="Test Destination",
    verification_request=False,
    verification_question='',
    verification_response='',
    asin="TESTASIN123",
    sku="TESTSKU123",
    fnsku="TESTFNSKU123",
    ean='',
    product_code='',
    serial_number='',
    state_amz="Test State",
    reason_amz="Test Reason",
    customer_notes=None,
    company='Selley',
    notes=None
)
print("Dati di prova inseriti correttamente")

