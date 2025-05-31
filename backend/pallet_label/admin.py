from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import PalletLabel


@admin.register(PalletLabel)
class PalletLabelAdmin(admin.ModelAdmin):
    """
    Configurazione admin per il modello PalletLabel aggiornato.
    """
    
    list_display = [
        'numero_spedizione',
        'nome_venditore', 
        'get_pallet_display',
        'numero_cartoni',
        'pdf_generated',
        'created_at'
    ]
    
    list_filter = [
        'nome_venditore',
        'pdf_generated',
        'created_at',
        'pallet_totale'
    ]
    
    search_fields = [
        'numero_spedizione',
        'nome_venditore',
        'nome_spedizione',
        'indirizzo_spedizione'
    ]
    
    readonly_fields = [
        'created_at',
        'updated_at',
        'get_pallet_display',
        'pdf_download_link'
    ]
    
    fieldsets = (
        ('Informazioni Base', {
            'fields': (
                'created_by',
                'created_at',
                'updated_at'
            )
        }),
        ('Dati Spedizione', {
            'fields': (
                'nome_venditore',
                'nome_spedizione',
                'numero_spedizione',
                'indirizzo_spedizione'
            )
        }),
        ('Dati Pallet', {
            'fields': (
                'pallet_numero',
                'pallet_totale',
                'get_pallet_display',
                'numero_cartoni'
            )
        }),
        ('PDF', {
            'fields': (
                'pdf_generated',
                'pdf_file',
                'pdf_download_link'
            )
        })
    )
    
    list_per_page = 25
    ordering = ['-created_at']
    
    def get_pallet_display(self, obj):
        """Mostra il display del pallet"""
        return obj.get_pallet_display()
    get_pallet_display.short_description = 'Pallet'
    get_pallet_display.admin_order_field = 'pallet_numero'
    
    def pdf_download_link(self, obj):
        """Link per scaricare il PDF"""
        if obj.pdf_file:
            url = reverse('pallet_label:download', args=[obj.pk])
            return format_html(
                '<a href="{}" target="_blank" class="button">📥 Scarica PDF</a>',
                url
            )
        return "PDF non disponibile"
    pdf_download_link.short_description = 'Download PDF'
    
    def get_queryset(self, request):
        """Ottimizza le query"""
        qs = super().get_queryset(request)
        return qs.select_related('created_by')
    
    def save_model(self, request, obj, form, change):
        """Imposta l'utente creatore se non presente"""
        if not change:  # Solo per nuovi oggetti
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
