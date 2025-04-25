from django.db import models

# Create your models here

class ProductReturn(models.Model):

    # Informazioni logistiche
    approved = models.BooleanField(default=False)
    box = models.IntegerField()  # Numero del box
    box_type = models.CharField(max_length=255)
    picked = models.DateField(null=True, blank=True)
    shipped = models.DateField(null=True, blank=True)

    # Identifiicazione di base
    lpn = models.CharField(max_length=255, unique=True)  # LPN unico
    brand = models.CharField(max_length=255)
    product_description = models.TextField()

    # Info stato e destinazione
    additional_info = models.CharField(max_length=255, null=True, blank=True)
    other_info = models.CharField(max_length=255, null=True, blank=True)
    destination = models.CharField(max_length=255)

    # Verifica del prodotto
    verification_request = models.BooleanField(default=False)
    verification_question = models.TextField(null=True, blank=True)
    verification_response = models.TextField(null=True, blank=True)

    # Codici aggiuntivi
    asin = models.CharField(max_length=255)
    sku = models.CharField(max_length=255)
    fnsku = models.CharField(max_length=255)
    ean = models.CharField(max_length=13, null=True, blank=True)  # Codice EAN
    #ELIMINATO product_code = models.CharField(max_length=255, blank=True)
    serial_number = models.CharField(max_length=255, null=True, blank=True)

    # Info Amazon e note utente
    state_amz = models.CharField(max_length=255)
    reason_amz = models.CharField(max_length=255)
    customer_notes = models.TextField(null=True, blank=True)

    # Dati aziendali
    company = models.CharField(max_length=255)

    # Note
    notes = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.product_description} ({self.lpn})"

