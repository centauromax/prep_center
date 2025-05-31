from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import PalletLabel


@admin.register(PalletLabel)
class PalletLabelAdmin(admin.ModelAdmin):
    """
    Configurazione admin per le etichette pallet.
    """
    
    list_display = [
        'pallet_id',
        'amazon_warehouse_code',
        'shipment_id',
        'pallet_description',
        'total_boxes',
        'pallet_weight',
        'created_by',
        'created_at',
        'pdf_status',
        'actions_column'
    ]
    
    list_filter = [
        'amazon_warehouse_code',
        'created_at',
        'pdf_generated',
        'created_by'
    ]
    
    search_fields = [
        'pallet_id',
        'shipment_id',
        'amazon_warehouse_code',
        'sender_name',
        'amazon_warehouse_name'
    ]
    
    readonly_fields = [
        'created_at',
        'updated_at',
        'total_volume_cbm',
        'pdf_status'
    ]
    
    fieldsets = (
        ('Informazioni Base', {
            'fields': (
                'created_by',
                'pallet_id',
                ('created_at', 'updated_at')
            )
        }),
        ('Mittente', {
            'fields': (
                'sender_name',
                'sender_address_line1',
                'sender_address_line2',
                ('sender_city', 'sender_postal_code'),
                'sender_country'
            )
        }),
        ('Destinatario Amazon', {
            'fields': (
                'amazon_warehouse_code',
                'amazon_warehouse_name',
                'amazon_address_line1',
                'amazon_address_line2',
                ('amazon_city', 'amazon_postal_code'),
                'amazon_country'
            )
        }),
        ('Spedizione', {
            'fields': (
                'shipment_id',
                'po_number',
                'carrier',
                'tracking_number'
            )
        }),
        ('Dettagli Pallet', {
            'fields': (
                ('pallet_count', 'pallet_number'),
                'total_boxes',
                'pallet_weight',
                ('pallet_dimensions_length', 'pallet_dimensions_width', 'pallet_dimensions_height'),
                'total_volume_cbm'
            )
        }),
        ('Istruzioni e Note', {
            'fields': (
                'special_instructions',
            )
        }),
        ('PDF', {
            'fields': (
                'pdf_generated',
                'pdf_file',
                'pdf_status'
            )
        })
    )
    
    def pdf_status(self, obj):
        """Mostra lo stato del PDF con icone colorate."""
        if obj.pdf_generated and obj.pdf_file:
            return format_html(
                '<span style="color: green;">✓ PDF Generato</span>'
            )
        else:
            return format_html(
                '<span style="color: red;">✗ PDF Non Generato</span>'
            )
    pdf_status.short_description = 'Stato PDF'
    
    def actions_column(self, obj):
        """Colonna con azioni rapide."""
        actions = []
        
        # Link per visualizzare
        view_url = reverse('admin:pallet_label_palletlabel_change', args=[obj.pk])
        actions.append(f'<a href="{view_url}" title="Modifica">📝</a>')
        
        # Link per scaricare PDF se disponibile
        if obj.pdf_file:
            download_url = reverse('pallet_label:download', args=[obj.pk])
            actions.append(f'<a href="{download_url}" title="Scarica PDF" target="_blank">📄</a>')
        
        return mark_safe(' | '.join(actions))
    actions_column.short_description = 'Azioni'
    
    def get_queryset(self, request):
        """Ottimizza le query per l'admin."""
        return super().get_queryset(request).select_related('created_by')
    
    def save_model(self, request, obj, form, change):
        """Salva il modello e genera il PDF se necessario."""
        if not change:  # Nuovo oggetto
            obj.created_by = request.user
        
        super().save_model(request, obj, form, change)
        
        # Genera PDF se non esiste
        if not obj.pdf_generated or not obj.pdf_file:
            try:
                from .pdf_generator import generate_pallet_label_pdf
                pdf_file = generate_pallet_label_pdf(obj)
                obj.pdf_file.save(pdf_file.name, pdf_file)
                obj.pdf_generated = True
                obj.save()
                
                self.message_user(request, f'PDF generato per l\'etichetta {obj.pallet_id}')
            except Exception as e:
                self.message_user(
                    request, 
                    f'Errore nella generazione del PDF: {str(e)}', 
                    level='ERROR'
                )
    
    class Media:
        css = {
            'all': ('admin/css/custom_admin.css',)
        }
        js = ('admin/js/pallet_label_admin.js',)
