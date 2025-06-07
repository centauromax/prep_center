from django.contrib import admin
from .models import PrepBusinessConfig, ShipmentStatusUpdate, OutgoingMessage, SearchResultItem, IncomingMessage, TelegramNotification, TelegramMessage

@admin.register(PrepBusinessConfig)
class PrepBusinessConfigAdmin(admin.ModelAdmin):
    list_display = ('api_url', 'is_active', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('api_url',)
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('api_url', 'api_key', 'is_active')
        }),
        ('Impostazioni avanzate', {
            'classes': ('collapse',),
            'fields': ('api_timeout', 'max_retries', 'retry_backoff')
        }),
        ('Timestamp', {
            'classes': ('collapse',),
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def save_model(self, request, obj, form, change):
        # Se la configurazione viene attivata, disattiva tutte le altre
        if obj.is_active:
            PrepBusinessConfig.objects.exclude(pk=obj.pk).update(is_active=False)
        super().save_model(request, obj, form, change)


@admin.register(ShipmentStatusUpdate)
class ShipmentStatusUpdateAdmin(admin.ModelAdmin):
    list_display = ('shipment_id', 'event_type', 'new_status', 'merchant_name', 'created_at', 'processed')
    list_filter = ('event_type', 'new_status', 'processed', 'created_at', 'entity_type')
    search_fields = ('shipment_id', 'merchant_name', 'tracking_number')
    readonly_fields = ('created_at', 'payload')
    fieldsets = (
        (None, {
            'fields': ('shipment_id', 'event_type', 'entity_type', 'processed')
        }),
        ('Stati', {
            'fields': ('previous_status', 'new_status')
        }),
        ('Dettagli', {
            'fields': ('merchant_id', 'merchant_name', 'tracking_number', 'carrier', 'notes')
        }),
        ('Dati tecnici', {
            'classes': ('collapse',),
            'fields': ('created_at', 'payload')
        }),
    )
    list_per_page = 20
    date_hierarchy = 'created_at'
    actions = ['mark_as_processed', 'mark_as_unprocessed']
    
    def mark_as_processed(self, request, queryset):
        updated = queryset.update(processed=True)
        self.message_user(request, f"{updated} aggiornamenti di stato contrassegnati come elaborati.")
    mark_as_processed.short_description = "Segna come elaborati"
    
    def mark_as_unprocessed(self, request, queryset):
        updated = queryset.update(processed=False)
        self.message_user(request, f"{updated} aggiornamenti di stato contrassegnati come non elaborati.")
    mark_as_unprocessed.short_description = "Segna come non elaborati"

@admin.register(IncomingMessage)
class IncomingMessageAdmin(admin.ModelAdmin):
    list_display = ('message_type', 'session_id', 'created_at', 'processed')
    list_filter = ('message_type', 'processed', 'created_at')
    search_fields = ('session_id', 'message_type')
    readonly_fields = ('created_at', 'processed_at')
    fieldsets = (
        (None, {
            'fields': ('message_type', 'session_id', 'processed')
        }),
        ('Contenuto', {
            'fields': ('payload',)
        }),
        ('Elaborazione', {
            'fields': ('processed_at', 'process_result')
        }),
        ('Timestamp', {
            'classes': ('collapse',),
            'fields': ('created_at',)
        }),
    )
    list_per_page = 20
    date_hierarchy = 'created_at'
    actions = ['mark_as_processed', 'mark_as_unprocessed']
    
    def mark_as_processed(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(processed=True, processed_at=timezone.now())
        self.message_user(request, f"{updated} messaggi contrassegnati come elaborati.")
    mark_as_processed.short_description = "Segna come elaborati"
    
    def mark_as_unprocessed(self, request, queryset):
        updated = queryset.update(processed=False, processed_at=None)
        self.message_user(request, f"{updated} messaggi contrassegnati come non elaborati.")
    mark_as_unprocessed.short_description = "Segna come non elaborati"

@admin.register(TelegramNotification)
class TelegramNotificationAdmin(admin.ModelAdmin):
    list_display = ('email', 'username', 'get_full_name', 'is_active', 'total_notifications_sent', 'last_notification_at', 'created_at')
    list_filter = ('is_active', 'language_code', 'created_at', 'last_notification_at')
    search_fields = ('email', 'username', 'first_name', 'last_name', 'chat_id')
    readonly_fields = ('created_at', 'updated_at', 'total_notifications_sent', 'last_notification_at')
    
    fieldsets = (
        (None, {
            'fields': ('email', 'chat_id', 'is_active')
        }),
        ('Informazioni Telegram', {
            'fields': ('username', 'first_name', 'last_name', 'language_code')
        }),
        ('Statistiche', {
            'classes': ('collapse',),
            'fields': ('total_notifications_sent', 'last_notification_at')
        }),
        ('Timestamp', {
            'classes': ('collapse',),
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    list_per_page = 25
    date_hierarchy = 'created_at'
    actions = ['activate_users', 'deactivate_users', 'send_test_message']
    
    def get_full_name(self, obj):
        return obj.get_full_name()
    get_full_name.short_description = "Nome completo"
    
    def activate_users(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} utenti Telegram attivati.")
    activate_users.short_description = "Attiva utenti selezionati"
    
    def deactivate_users(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} utenti Telegram disattivati.")
    deactivate_users.short_description = "Disattiva utenti selezionati"
    
    def send_test_message(self, request, queryset):
        from .services import send_telegram_notification
        success_count = 0
        
        for user in queryset.filter(is_active=True):
            try:
                send_telegram_notification(
                    user.email, 
                    "🔧 Messaggio di test dal FBA Prep Center Italy!\n\nSe ricevi questo messaggio, le notifiche Telegram sono configurate correttamente."
                )
                success_count += 1
            except Exception as e:
                self.message_user(request, f"Errore nell'inviare messaggio a {user.email}: {str(e)}", level='ERROR')
        
        if success_count > 0:
            self.message_user(request, f"Messaggio di test inviato a {success_count} utenti.")
    send_test_message.short_description = "Invia messaggio di test"


@admin.register(TelegramMessage)
class TelegramMessageAdmin(admin.ModelAdmin):
    list_display = ('telegram_user', 'get_message_preview', 'status', 'event_type', 'shipment_id', 'retry_count', 'created_at', 'sent_at')
    list_filter = ('status', 'event_type', 'created_at', 'sent_at')
    search_fields = ('telegram_user__email', 'message_text', 'shipment_id')
    readonly_fields = ('created_at', 'sent_at', 'telegram_message_id')
    
    fieldsets = (
        (None, {
            'fields': ('telegram_user', 'status', 'message_text')
        }),
        ('Dettagli', {
            'fields': ('event_type', 'shipment_id', 'telegram_message_id')
        }),
        ('Errori e retry', {
            'classes': ('collapse',),
            'fields': ('error_message', 'retry_count')
        }),
        ('Timestamp', {
            'classes': ('collapse',),
            'fields': ('created_at', 'sent_at')
        }),
    )
    
    list_per_page = 25
    date_hierarchy = 'created_at'
    actions = ['retry_failed_messages', 'mark_as_sent']
    
    def get_message_preview(self, obj):
        return (obj.message_text[:50] + '...') if len(obj.message_text) > 50 else obj.message_text
    get_message_preview.short_description = "Anteprima messaggio"
    
    def retry_failed_messages(self, request, queryset):
        from .services import retry_telegram_message
        success_count = 0
        
        for message in queryset.filter(status__in=['failed', 'retry']):
            try:
                if retry_telegram_message(message):
                    success_count += 1
            except Exception as e:
                self.message_user(request, f"Errore nel ritentare messaggio {message.id}: {str(e)}", level='ERROR')
        
        if success_count > 0:
            self.message_user(request, f"{success_count} messaggi riprovati con successo.")
    retry_failed_messages.short_description = "Riprova messaggi falliti"
    
    def mark_as_sent(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(status='sent', sent_at=timezone.now())
        self.message_user(request, f"{updated} messaggi contrassegnati come inviati.")
    mark_as_sent.short_description = "Segna come inviati"
