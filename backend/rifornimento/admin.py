from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import Product, RifornimentoRequest, RifornimentoItem


class RifornimentoItemInline(admin.TabularInline):
    """Inline admin per gestire elementi rifornimento dentro le richieste"""
    model = RifornimentoItem
    extra = 1
    fields = ['product', 'quantity', 'quantity_approved', 'quantity_ordered', 'quantity_received', 
              'unit_cost', 'total_cost', 'reason']
    readonly_fields = ['total_cost']
    
    def get_extra(self, request, obj=None, **kwargs):
        """Non mostrare campi extra se si sta modificando"""
        if obj:
            return 0
        return 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """Configurazione admin per modello Product"""
    list_display = ['sku', 'title', 'brand', 'current_stock', 'minimum_stock', 'needs_restocking_badge', 
                    'sales_velocity', 'is_active', 'updated_at']
    list_filter = ['is_active', 'brand', 'condition', 'created_at']
    search_fields = ['sku', 'title', 'asin', 'fnsku', 'ean', 'brand']
    readonly_fields = ['created_at', 'updated_at', 'needs_restocking', 'suggested_order_quantity', 'days_of_inventory']
    
    fieldsets = [
        ('Identificatori', {
            'fields': ['sku', 'asin', 'fnsku', 'ean']
        }),
        ('Informazioni Prodotto', {
            'fields': ['title', 'brand', 'condition', 'notes']
        }),
        ('Dimensioni e Peso', {
            'fields': ['length_mm', 'width_mm', 'height_mm', 'weight_gm'],
            'classes': ['collapse']
        }),
        ('Inventario e Rifornimento', {
            'fields': ['current_stock', 'minimum_stock', 'optimal_stock', 'needs_restocking', 
                      'suggested_order_quantity', 'days_of_inventory']
        }),
        ('Costi e Vendite', {
            'fields': ['cost_per_unit', 'sales_velocity'],
            'classes': ['collapse']
        }),
        ('Metadati', {
            'fields': ['is_active', 'created_by', 'created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]
    
    list_per_page = 50
    ordering = ['brand', 'title']
    
    def needs_restocking_badge(self, obj):
        """Badge colorato per indicare se serve rifornimento"""
        if obj.needs_restocking:
            return format_html(
                '<span style="color: white; background-color: #dc3545; padding: 3px 8px; border-radius: 3px; font-size: 11px;">'
                'RIFORNIRE'
                '</span>'
            )
        return format_html(
            '<span style="color: white; background-color: #28a745; padding: 3px 8px; border-radius: 3px; font-size: 11px;">'
            'OK'
            '</span>'
        )
    needs_restocking_badge.short_description = 'Rifornimento'
    needs_restocking_badge.admin_order_field = 'current_stock'
    
    def save_model(self, request, obj, form, change):
        """Salva il modello impostando created_by se nuovo"""
        if not change:  # Se è un nuovo oggetto
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(RifornimentoRequest)
class RifornimentoRequestAdmin(admin.ModelAdmin):
    """Configurazione admin per modello RifornimentoRequest"""
    list_display = ['request_number', 'title', 'status_badge', 'priority_badge', 'requested_by', 
                    'total_items', 'total_quantity', 'needed_by', 'is_overdue_badge', 'created_at']
    list_filter = ['status', 'priority', 'requested_by', 'created_at', 'needed_by']
    search_fields = ['request_number', 'title', 'supplier', 'notes']
    readonly_fields = ['request_number', 'total_items', 'total_quantity', 'is_overdue', 
                      'created_at', 'updated_at']
    
    fieldsets = [
        ('Informazioni Generali', {
            'fields': ['request_number', 'title', 'status', 'priority']
        }),
        ('Date', {
            'fields': ['request_date', 'needed_by', 'approved_date', 'order_date', 
                      'expected_delivery', 'actual_delivery']
        }),
        ('Persone Coinvolte', {
            'fields': ['requested_by', 'approved_by']
        }),
        ('Fornitore', {
            'fields': ['supplier', 'supplier_reference'],
            'classes': ['collapse']
        }),
        ('Costi', {
            'fields': ['total_cost', 'shipping_cost'],
            'classes': ['collapse']
        }),
        ('Note', {
            'fields': ['notes', 'internal_notes'],
            'classes': ['collapse']
        }),
        ('Statistiche', {
            'fields': ['total_items', 'total_quantity', 'is_overdue'],
            'classes': ['collapse']
        }),
        ('Metadati', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]
    
    inlines = [RifornimentoItemInline]
    list_per_page = 25
    ordering = ['-created_at']
    
    def status_badge(self, obj):
        """Badge colorato per lo stato"""
        colors = {
            'draft': '#6c757d',
            'pending': '#ffc107',
            'approved': '#17a2b8',
            'ordered': '#007bff',
            'shipped': '#fd7e14',
            'received': '#28a745',
            'cancelled': '#dc3545',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="color: white; background-color: {}; padding: 3px 8px; border-radius: 3px; font-size: 11px;">'
            '{}'
            '</span>',
            color, obj.get_status_display().upper()
        )
    status_badge.short_description = 'Stato'
    status_badge.admin_order_field = 'status'
    
    def priority_badge(self, obj):
        """Badge colorato per la priorità"""
        colors = {
            'low': '#28a745',
            'normal': '#17a2b8', 
            'high': '#ffc107',
            'urgent': '#dc3545',
        }
        color = colors.get(obj.priority, '#17a2b8')
        return format_html(
            '<span style="color: white; background-color: {}; padding: 3px 8px; border-radius: 3px; font-size: 11px;">'
            '{}'
            '</span>',
            color, obj.get_priority_display().upper()
        )
    priority_badge.short_description = 'Priorità'
    priority_badge.admin_order_field = 'priority'
    
    def is_overdue_badge(self, obj):
        """Badge per indicare se è in ritardo"""
        if obj.is_overdue:
            return format_html(
                '<span style="color: white; background-color: #dc3545; padding: 3px 8px; border-radius: 3px; font-size: 11px;">'
                'IN RITARDO'
                '</span>'
            )
        return format_html(
            '<span style="color: white; background-color: #28a745; padding: 3px 8px; border-radius: 3px; font-size: 11px;">'
            'NEI TEMPI'
            '</span>'
        )
    is_overdue_badge.short_description = 'Tempistiche'
    is_overdue_badge.admin_order_field = 'needed_by'
    
    def save_model(self, request, obj, form, change):
        """Salva il modello impostando requested_by se nuovo"""
        if not change:  # Se è un nuovo oggetto
            obj.requested_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(RifornimentoItem)
class RifornimentoItemAdmin(admin.ModelAdmin):
    """Configurazione admin per modello RifornimentoItem"""
    list_display = ['request_link', 'product_link', 'quantity', 'quantity_approved', 
                    'quantity_ordered', 'quantity_received', 'quantity_pending', 
                    'is_fully_received_badge', 'total_cost']
    list_filter = ['request__status', 'request__priority', 'product__brand', 'created_at']
    search_fields = ['request__request_number', 'request__title', 'product__sku', 
                    'product__title', 'product__brand']
    readonly_fields = ['total_cost', 'quantity_pending', 'is_fully_received', 'created_at', 'updated_at']
    
    fieldsets = [
        ('Relazioni', {
            'fields': ['request', 'product']
        }),
        ('Quantità', {
            'fields': ['quantity', 'quantity_approved', 'quantity_ordered', 'quantity_received',
                      'quantity_pending', 'is_fully_received']
        }),
        ('Costi', {
            'fields': ['unit_cost', 'total_cost']
        }),
        ('Note', {
            'fields': ['reason', 'priority_notes'],
            'classes': ['collapse']
        }),
        ('Metadati', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]
    
    list_per_page = 50
    ordering = ['-created_at']
    
    def request_link(self, obj):
        """Link alla richiesta di rifornimento"""
        url = reverse('admin:rifornimento_rifornimentorequest_change', args=[obj.request.pk])
        return format_html('<a href="{}">{}</a>', url, obj.request.request_number)
    request_link.short_description = 'Richiesta'
    request_link.admin_order_field = 'request__request_number'
    
    def product_link(self, obj):
        """Link al prodotto"""
        url = reverse('admin:rifornimento_product_change', args=[obj.product.pk])
        return format_html('<a href="{}">{}</a>', url, obj.product.sku)
    product_link.short_description = 'Prodotto'
    product_link.admin_order_field = 'product__sku'
    
    def is_fully_received_badge(self, obj):
        """Badge per indicare se completamente ricevuto"""
        if obj.is_fully_received:
            return format_html(
                '<span style="color: white; background-color: #28a745; padding: 3px 8px; border-radius: 3px; font-size: 11px;">'
                'COMPLETO'
                '</span>'
            )
        return format_html(
            '<span style="color: white; background-color: #ffc107; padding: 3px 8px; border-radius: 3px; font-size: 11px;">'
            'PARZIALE'
            '</span>'
        )
    is_fully_received_badge.short_description = 'Ricevuto'
    is_fully_received_badge.admin_order_field = 'quantity_received'


# Personalizzazione titoli admin
admin.site.site_header = "Prep Center - Amministrazione Rifornimenti"
admin.site.site_title = "Rifornimenti Admin"
admin.site.index_title = "Gestione Rifornimenti"
