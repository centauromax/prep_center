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

class OutgoingMessage(models.Model):
    """Coda di messaggi per la comunicazione con l'estensione Chrome."""
    MESSAGE_TYPES = [
        ('OUTBOUND_WITHOUT_INBOUND', 'Outbound without inbound'),
        ('BOX_SERVICES_REQUEST', 'Box Services Request'),
    ]
    message_id = models.CharField(verbose_name="Tipo messaggio", max_length=100, choices=MESSAGE_TYPES)
    parameters = models.JSONField(verbose_name="Parametri messaggio", null=True, blank=True)
    created_at = models.DateTimeField(verbose_name="Data creazione", auto_now_add=True)
    consumed = models.BooleanField(verbose_name="Consumto", default=False)
    consumed_at = models.DateTimeField(verbose_name="Data consumo", null=True, blank=True)

    class Meta:
        verbose_name = "Messaggio in coda"
        verbose_name_plural = "Messaggi in coda"

    def __str__(self):
        return f"{self.message_id} ({self.id})"

class IncomingMessage(models.Model):
    """Coda di messaggi dall'estensione Chrome verso l'app."""
    MESSAGE_TYPES = [
        ('USER_RESPONSE', 'Risposta utente'),
        ('EXTENSION_STATUS', 'Status estensione'),
        ('ACTION_COMPLETED', 'Azione completata'),
        ('ERROR_REPORT', 'Segnalazione errore'),
    ]
    
    message_type = models.CharField(verbose_name="Tipo messaggio", max_length=100, choices=MESSAGE_TYPES)
    payload = models.JSONField(verbose_name="Payload messaggio", null=True, blank=True)
    session_id = models.CharField(verbose_name="ID Sessione", max_length=100, null=True, blank=True, 
                                 help_text="ID per correlare richiesta/risposta")
    created_at = models.DateTimeField(verbose_name="Data ricezione", auto_now_add=True)
    processed = models.BooleanField(verbose_name="Elaborato", default=False)
    processed_at = models.DateTimeField(verbose_name="Data elaborazione", null=True, blank=True)
    process_result = models.JSONField(verbose_name="Risultato elaborazione", null=True, blank=True)

    class Meta:
        verbose_name = "Messaggio in entrata"
        verbose_name_plural = "Messaggi in entrata"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.message_type} ({self.session_id or self.id})"

class SearchResultItem(models.Model):
    """
    Modello per memorizzare un singolo item trovato durante la ricerca spedizioni.
    """
    search_id = models.CharField(max_length=36, null=True, blank=True)  # UUID per raggruppare i risultati
    shipment_type = models.CharField(max_length=36, null=True, blank=True)  # Tipo di spedizione (inbound/outbound)
    shipment_name = models.CharField(max_length=255, null=True, blank=True)
    product_title = models.CharField(max_length=255, null=True, blank=True)
    product_sku = models.CharField(max_length=255, null=True, blank=True)
    product_asin = models.CharField(max_length=255, null=True, blank=True)
    product_fnsku = models.CharField(max_length=255, null=True, blank=True)
    product_quantity = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    processing_status = models.CharField(max_length=20, choices=[
        ('in_progress', 'In Progress'),
        ('complete', 'Complete'),
        ('error', 'Error')
    ], default='complete')

    def __str__(self):
        return f"{self.product_title} ({self.shipment_name})"

    class Meta:
        ordering = ['shipment_name', 'product_title']
        verbose_name = "Risultato Ricerca Item"
        verbose_name_plural = "Risultati Ricerca Items"


class TelegramNotification(models.Model):
    """
    Modello per gestire le notifiche Telegram dei clienti.
    Collega l'email del software Prep Center con il chat_id Telegram.
    """
    email = models.EmailField(
        verbose_name="Email Prep Center", 
        help_text="Email utilizzata nell'account del cliente sul software del Prep Center"
    )
    chat_id = models.BigIntegerField(
        verbose_name="Chat ID Telegram", 
        unique=True,
        help_text="ID della chat Telegram per l'invio di notifiche"
    )
    username = models.CharField(
        verbose_name="Username Telegram", 
        max_length=100, 
        null=True, 
        blank=True
    )
    first_name = models.CharField(
        verbose_name="Nome", 
        max_length=100, 
        null=True, 
        blank=True
    )
    last_name = models.CharField(
        verbose_name="Cognome", 
        max_length=100, 
        null=True, 
        blank=True
    )
    is_active = models.BooleanField(
        verbose_name="Attivo", 
        default=True,
        help_text="Se disattivato, non riceverà notifiche"
    )
    language_code = models.CharField(
        verbose_name="Codice lingua", 
        max_length=10, 
        null=True, 
        blank=True,
        default='it'
    )
    created_at = models.DateTimeField(verbose_name="Data registrazione", auto_now_add=True)
    updated_at = models.DateTimeField(verbose_name="Ultimo aggiornamento", auto_now=True)
    last_notification_at = models.DateTimeField(
        verbose_name="Ultima notifica", 
        null=True, 
        blank=True
    )
    
    # Statistiche
    total_notifications_sent = models.PositiveIntegerField(
        verbose_name="Notifiche inviate", 
        default=0
    )
    
    class Meta:
        verbose_name = "Notifica Telegram"
        verbose_name_plural = "Notifiche Telegram"
        ordering = ['-created_at']
        # Una persona può registrarsi più volte con email diversa, 
        # ma stesso chat_id può avere solo una email
        unique_together = [['email', 'chat_id']]
    
    def __str__(self):
        return f"{self.email} -> @{self.username or 'N/A'}"
    
    def get_full_name(self):
        """Restituisce il nome completo dell'utente."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.username:
            return f"@{self.username}"
        else:
            return self.email
    
    def increment_notification_count(self):
        """Incrementa il contatore delle notifiche inviate."""
        from django.utils import timezone
        self.total_notifications_sent += 1
        self.last_notification_at = timezone.now()
        self.save(update_fields=['total_notifications_sent', 'last_notification_at'])


class TelegramMessage(models.Model):
    """
    Log dei messaggi Telegram inviati per il debugging e statistiche.
    """
    STATUS_CHOICES = [
        ('pending', 'In attesa'),
        ('sent', 'Inviato'),
        ('failed', 'Fallito'),
        ('retry', 'Da riprovare'),
    ]
    
    telegram_user = models.ForeignKey(
        TelegramNotification, 
        on_delete=models.CASCADE,
        verbose_name="Utente Telegram"
    )
    message_text = models.TextField(verbose_name="Testo messaggio")
    status = models.CharField(
        verbose_name="Stato", 
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='pending'
    )
    telegram_message_id = models.BigIntegerField(
        verbose_name="ID Messaggio Telegram", 
        null=True, 
        blank=True
    )
    error_message = models.TextField(
        verbose_name="Messaggio errore", 
        null=True, 
        blank=True
    )
    retry_count = models.PositiveIntegerField(verbose_name="Tentativi", default=0)
    created_at = models.DateTimeField(verbose_name="Data creazione", auto_now_add=True)
    sent_at = models.DateTimeField(verbose_name="Data invio", null=True, blank=True)
    
    # Metadati opzionali
    event_type = models.CharField(
        verbose_name="Tipo evento", 
        max_length=100, 
        null=True, 
        blank=True,
        help_text="Tipo di evento che ha generato il messaggio"
    )
    shipment_id = models.CharField(
        verbose_name="ID Spedizione", 
        max_length=100, 
        null=True, 
        blank=True
    )
    
    class Meta:
        verbose_name = "Messaggio Telegram"
        verbose_name_plural = "Messaggi Telegram"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.telegram_user.email}: {self.message_text[:50]}..."


class TelegramConversation(models.Model):
    """
    Modello per gestire le conversazioni bidirezionali tra clienti e admin.
    """
    customer_email = models.EmailField(
        verbose_name="Email Cliente",
        help_text="Email del cliente partecipante alla conversazione"
    )
    thread_id = models.CharField(
        verbose_name="ID Thread",
        max_length=50,
        unique=True,
        help_text="ID univoco per il thread di conversazione"
    )
    is_active = models.BooleanField(
        verbose_name="Conversazione Attiva",
        default=True,
        help_text="Se False, la conversazione è chiusa"
    )
    created_at = models.DateTimeField(verbose_name="Data inizio", auto_now_add=True)
    updated_at = models.DateTimeField(verbose_name="Ultimo aggiornamento", auto_now=True)
    last_message_at = models.DateTimeField(
        verbose_name="Ultimo messaggio",
        null=True,
        blank=True
    )
    
    class Meta:
        verbose_name = "Conversazione Telegram"
        verbose_name_plural = "Conversazioni Telegram"
        ordering = ['-last_message_at', '-updated_at']
    
    def __str__(self):
        status = "Attiva" if self.is_active else "Chiusa"
        return f"Conversazione {self.thread_id} - {self.customer_email} ({status})"
    
    def get_customer_alias(self):
        """Genera un alias breve per il cliente (A, B, C...)"""
        try:
            # Semplice mapping basato sull'ordine di creazione
            conversations = TelegramConversation.objects.filter(
                created_at__lte=self.created_at,
                is_active=True
            ).order_by('created_at')
            
            # Usa enumerate per evitare errori di index
            for index, conv in enumerate(conversations):
                if conv.id == self.id:
                    return chr(65 + (index % 26))  # A, B, C, ..., Z
            
            # Fallback se non trovato
            return 'X'
        except Exception:
            # Fallback sicuro in caso di errore
            return 'X'


class TelegramChatMessage(models.Model):
    """
    Modello per memorizzare i messaggi delle conversazioni bidirezionali.
    """
    MESSAGE_TYPES = [
        ('customer_to_admin', 'Cliente -> Admin'),
        ('admin_to_customer', 'Admin -> Cliente'),
        ('admin_broadcast', 'Admin -> Tutti'),
        ('system', 'Sistema')
    ]
    
    conversation = models.ForeignKey(
        TelegramConversation,
        on_delete=models.CASCADE,
        verbose_name="Conversazione",
        related_name="messages"
    )
    sender_chat_id = models.BigIntegerField(
        verbose_name="Chat ID Mittente",
        help_text="Chat ID di chi ha inviato il messaggio"
    )
    sender_email = models.EmailField(
        verbose_name="Email Mittente",
        help_text="Email di chi ha inviato il messaggio"
    )
    message_type = models.CharField(
        verbose_name="Tipo Messaggio",
        max_length=20,
        choices=MESSAGE_TYPES,
        default='customer_to_admin'
    )
    message_text = models.TextField(verbose_name="Testo Messaggio")
    created_at = models.DateTimeField(verbose_name="Data invio", auto_now_add=True)
    
    # Metadati per tracking delivery
    delivered_to = models.JSONField(
        verbose_name="Consegnato a",
        null=True,
        blank=True,
        help_text="Lista di chat_id a cui è stato consegnato il messaggio"
    )
    
    # Informazioni di reply (se questo messaggio è una risposta)
    reply_to_message = models.JSONField(
        verbose_name="Risposta a messaggio",
        null=True,
        blank=True,
        help_text="Informazioni del messaggio originale a cui si sta rispondendo"
    )
    
    class Meta:
        verbose_name = "Messaggio Chat"
        verbose_name_plural = "Messaggi Chat"
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.conversation.thread_id} - {self.sender_email}: {self.message_text[:50]}..."


class AdminActiveConversation(models.Model):
    """
    Modello per tracciare le conversazioni attive per ogni admin.
    """
    admin_chat_id = models.BigIntegerField(
        verbose_name="Chat ID Admin",
        unique=True,
        help_text="Chat ID dell'admin"
    )
    active_conversation = models.ForeignKey(
        TelegramConversation,
        on_delete=models.CASCADE,
        verbose_name="Conversazione Attiva",
        null=True,
        blank=True
    )
    updated_at = models.DateTimeField(verbose_name="Ultimo aggiornamento", auto_now=True)
    
    class Meta:
        verbose_name = "Conversazione Attiva Admin"
        verbose_name_plural = "Conversazioni Attive Admin"
    
    def __str__(self):
        if self.active_conversation:
            return f"Admin {self.admin_chat_id} -> {self.active_conversation.customer_email}"
        return f"Admin {self.admin_chat_id} (nessuna conversazione attiva)"
