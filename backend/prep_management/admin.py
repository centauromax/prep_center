from django.contrib import admin
from .models import PrepBusinessConfig, ShipmentStatusUpdate, OutgoingMessage, SearchResultItem, IncomingMessage

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
