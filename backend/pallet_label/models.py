from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class PalletLabel(models.Model):
    """
    Modello per gestire le etichette dei pallet destinati ad Amazon.
    """
    
    # Informazioni di base
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Creato da")
    created_at = models.DateTimeField(default=timezone.now, verbose_name="Data creazione")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Ultimo aggiornamento")
    
    # Informazioni del pallet
    pallet_id = models.CharField(max_length=100, verbose_name="ID Pallet", help_text="Identificativo univoco del pallet")
    
    # Informazioni del mittente
    sender_name = models.CharField(max_length=200, verbose_name="Nome mittente")
    sender_address_line1 = models.CharField(max_length=200, verbose_name="Indirizzo mittente (riga 1)")
    sender_address_line2 = models.CharField(max_length=200, blank=True, verbose_name="Indirizzo mittente (riga 2)")
    sender_city = models.CharField(max_length=100, verbose_name="Città mittente")
    sender_postal_code = models.CharField(max_length=20, verbose_name="CAP mittente")
    sender_country = models.CharField(max_length=100, default="Italia", verbose_name="Paese mittente")
    
    # Informazioni del destinatario (Amazon)
    amazon_warehouse_code = models.CharField(max_length=10, verbose_name="Codice warehouse Amazon", help_text="Es: MXP5, LIN1, etc.")
    amazon_warehouse_name = models.CharField(max_length=200, verbose_name="Nome warehouse Amazon")
    amazon_address_line1 = models.CharField(max_length=200, verbose_name="Indirizzo Amazon (riga 1)")
    amazon_address_line2 = models.CharField(max_length=200, blank=True, verbose_name="Indirizzo Amazon (riga 2)")
    amazon_city = models.CharField(max_length=100, verbose_name="Città Amazon")
    amazon_postal_code = models.CharField(max_length=20, verbose_name="CAP Amazon")
    amazon_country = models.CharField(max_length=100, default="Italia", verbose_name="Paese Amazon")
    
    # Informazioni della spedizione
    shipment_id = models.CharField(max_length=100, verbose_name="ID Spedizione", help_text="Shipment ID di Amazon")
    po_number = models.CharField(max_length=100, blank=True, verbose_name="Numero PO", help_text="Purchase Order Number")
    
    # Dettagli del pallet
    pallet_count = models.PositiveIntegerField(default=1, verbose_name="Numero di pallet")
    pallet_number = models.PositiveIntegerField(default=1, verbose_name="Numero pallet corrente", help_text="Es: 1 di 3")
    total_boxes = models.PositiveIntegerField(verbose_name="Numero totale scatole")
    pallet_weight = models.DecimalField(max_digits=8, decimal_places=2, verbose_name="Peso pallet (kg)")
    pallet_dimensions_length = models.DecimalField(max_digits=6, decimal_places=2, verbose_name="Lunghezza (cm)")
    pallet_dimensions_width = models.DecimalField(max_digits=6, decimal_places=2, verbose_name="Larghezza (cm)")
    pallet_dimensions_height = models.DecimalField(max_digits=6, decimal_places=2, verbose_name="Altezza (cm)")
    
    # Informazioni aggiuntive
    carrier = models.CharField(max_length=100, blank=True, verbose_name="Corriere", help_text="Nome del corriere")
    tracking_number = models.CharField(max_length=100, blank=True, verbose_name="Numero di tracking")
    special_instructions = models.TextField(blank=True, verbose_name="Istruzioni speciali")
    
    # Metadati
    pdf_generated = models.BooleanField(default=False, verbose_name="PDF generato")
    pdf_file = models.FileField(upload_to='pallet_labels/', blank=True, null=True, verbose_name="File PDF")
    
    class Meta:
        verbose_name = "Etichetta Pallet"
        verbose_name_plural = "Etichette Pallet"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Pallet {self.pallet_id} - {self.amazon_warehouse_code}"
    
    @property
    def pallet_description(self):
        """Descrizione del pallet per l'etichetta"""
        return f"Pallet {self.pallet_number} di {self.pallet_count}"
    
    @property
    def total_volume_cbm(self):
        """Calcola il volume in metri cubi"""
        if all([self.pallet_dimensions_length, self.pallet_dimensions_width, self.pallet_dimensions_height]):
            volume_cm3 = float(self.pallet_dimensions_length) * float(self.pallet_dimensions_width) * float(self.pallet_dimensions_height)
            return volume_cm3 / 1000000  # Converti da cm³ a m³
        return 0
