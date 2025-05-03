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
    
    # Tipi di evento
    EVENT_TYPES = [
        ('inbound_shipment.created', 'Spedizione in entrata creata'),
        ('inbound_shipment.notes_updated', 'Note spedizione in entrata aggiornate'),
        ('inbound_shipment.shipped', 'Spedizione in entrata spedita'),
        ('inbound_shipment.received', 'Spedizione in entrata ricevuta'),
        ('outbound_shipment.created', 'Spedizione in uscita creata'),
        ('outbound_shipment.shipped', 'Spedizione in uscita spedita'),
        ('outbound_shipment.notes_updated', 'Note spedizione in uscita aggiornate'),
        ('outbound_shipment.closed', 'Spedizione in uscita chiusa'),
        ('order.created', 'Ordine creato'),
        ('order.shipped', 'Ordine spedito'),
        ('invoice.created', 'Fattura creata'),
        ('other', 'Altro'),
    ]
    
    # Status possibili (manteniamo anche questi per retrocompatibilità)
    STATUS_CHOICES = [
        ('pending', 'In attesa'),
        ('processing', 'In elaborazione'),
        ('ready', 'Pronto'),
        ('shipped', 'Spedito'),
        ('delivered', 'Consegnato'),
        ('cancelled', 'Annullato'),
        ('failed', 'Fallito'),
        ('returned', 'Restituito'),
        ('created', 'Creato'),
        ('received', 'Ricevuto'),
        ('notes_updated', 'Note aggiornate'),
        ('closed', 'Chiuso'),
        ('other', 'Altro'),
    ]
    
    shipment_id = models.CharField(verbose_name="ID Spedizione", max_length=100)
    event_type = models.CharField(verbose_name="Tipo evento", max_length=100, choices=EVENT_TYPES, default='other')
    previous_status = models.CharField(verbose_name="Stato precedente", max_length=50, choices=STATUS_CHOICES, null=True, blank=True)
    new_status = models.CharField(verbose_name="Nuovo stato", max_length=50, choices=STATUS_CHOICES)
    merchant_id = models.CharField(verbose_name="ID Merchant", max_length=100, null=True, blank=True)
    merchant_name = models.CharField(verbose_name="Nome Merchant", max_length=255, null=True, blank=True)
    tracking_number = models.CharField(verbose_name="Numero tracciamento", max_length=100, null=True, blank=True)
    carrier = models.CharField(verbose_name="Corriere", max_length=100, null=True, blank=True)
    entity_type = models.CharField(verbose_name="Tipo entità", max_length=50, null=True, blank=True, 
                                  help_text="Tipo di entità (inbound_shipment, outbound_shipment, order, invoice)")
    notes = models.TextField(verbose_name="Note", null=True, blank=True)
    payload = models.JSONField(verbose_name="Payload completo", null=True, blank=True)
    created_at = models.DateTimeField(verbose_name="Data ricezione", auto_now_add=True)
    
    # Campi per l'elaborazione
    processed = models.BooleanField(verbose_name="Elaborato", default=False)
    processed_at = models.DateTimeField(verbose_name="Data elaborazione", null=True, blank=True)
    process_success = models.BooleanField(verbose_name="Elaborazione riuscita", null=True, blank=True)
    process_message = models.TextField(verbose_name="Messaggio elaborazione", null=True, blank=True)
    process_result = models.JSONField(verbose_name="Risultato elaborazione", null=True, blank=True)
    
    # Campi per relazioni
    related_shipment_id = models.CharField(verbose_name="ID Spedizione correlata", max_length=100, null=True, blank=True,
                                         help_text="ID di una spedizione correlata a questa (es. spedizione in entrata correlata a una in uscita)")
    
    class Meta:
        verbose_name = "Aggiornamento stato spedizione"
        verbose_name_plural = "Aggiornamenti stato spedizioni"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"#{self.shipment_id}: {self.event_type}"
        
    def get_event_name(self):
        """Restituisce il nome leggibile dell'evento."""
        return dict(self.EVENT_TYPES).get(self.event_type, self.event_type)
    
    def get_status_label(self):
        """Restituisce l'etichetta del nuovo stato."""
        return dict(self.STATUS_CHOICES).get(self.new_status, self.new_status)
