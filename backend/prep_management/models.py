from django.db import models
# Create your models here.

class PrepBusinessConfig(models.Model):
    """Configurazione per l'API di Prep Business."""
    api_url = models.URLField(verbose_name="URL API", max_length=255, default="https://dashboard.fbaprepcenteritaly.com/api")
    api_key = models.CharField(verbose_name="API Key", max_length=255)
    api_timeout = models.PositiveIntegerField(verbose_name="Timeout (secondi)", default=30)
    max_retries = models.PositiveIntegerField(verbose_name="Tentativi massimi", default=3)
    retry_backoff = models.FloatField(verbose_name="Backoff (secondi)", default=0.5)
    is_active = models.BooleanField(verbose_name="Attivo", default=True)
    created_at = models.DateTimeField(verbose_name="Data creazione", auto_now_add=True)
    updated_at = models.DateTimeField(verbose_name="Ultimo aggiornamento", auto_now=True)
    
    class Meta:
        verbose_name = "Configurazione Prep Business"
        verbose_name_plural = "Configurazioni Prep Business"
    
    def __str__(self):
        return f"Configurazione API ({self.api_url})"
    
    @classmethod
    def get_active_config(cls):
        """Ottiene la configurazione attiva."""
        return cls.objects.filter(is_active=True).first()


class ShipmentStatusUpdate(models.Model):
    """Notifica di cambio stato di una spedizione."""
    
    # Status possibili
    STATUS_CHOICES = [
        ('pending', 'In attesa'),
        ('processing', 'In elaborazione'),
        ('ready', 'Pronto'),
        ('shipped', 'Spedito'),
        ('delivered', 'Consegnato'),
        ('cancelled', 'Annullato'),
        ('failed', 'Fallito'),
        ('returned', 'Restituito'),
        ('other', 'Altro'),
    ]
    
    shipment_id = models.CharField(verbose_name="ID Spedizione", max_length=100)
    previous_status = models.CharField(verbose_name="Stato precedente", max_length=50, choices=STATUS_CHOICES, null=True, blank=True)
    new_status = models.CharField(verbose_name="Nuovo stato", max_length=50, choices=STATUS_CHOICES)
    merchant_id = models.CharField(verbose_name="ID Merchant", max_length=100, null=True, blank=True)
    merchant_name = models.CharField(verbose_name="Nome Merchant", max_length=255, null=True, blank=True)
    tracking_number = models.CharField(verbose_name="Numero tracciamento", max_length=100, null=True, blank=True)
    carrier = models.CharField(verbose_name="Corriere", max_length=100, null=True, blank=True)
    payload = models.JSONField(verbose_name="Payload completo", null=True, blank=True)
    created_at = models.DateTimeField(verbose_name="Data ricezione", auto_now_add=True)
    processed = models.BooleanField(verbose_name="Elaborato", default=False)
    
    class Meta:
        verbose_name = "Aggiornamento stato spedizione"
        verbose_name_plural = "Aggiornamenti stato spedizioni"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Spedizione {self.shipment_id}: {self.previous_status} → {self.new_status}"
