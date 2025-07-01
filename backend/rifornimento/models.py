from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.utils import timezone
from decimal import Decimal


class Product(models.Model):
    """
    Modello per memorizzare informazioni sui prodotti per il rifornimento.
    Integra dati da diverse fonti (SP-API, PrepBusiness, etc.)
    """
    # Identificatori prodotto
    sku = models.CharField(max_length=255, unique=True, verbose_name="SKU", help_text="Stock Keeping Unit")
    asin = models.CharField(max_length=50, blank=True, null=True, verbose_name="ASIN", help_text="Amazon Standard Identification Number")
    fnsku = models.CharField(max_length=50, blank=True, null=True, verbose_name="FNSKU", help_text="Fulfillment Network SKU")
    ean = models.CharField(max_length=13, blank=True, null=True, verbose_name="EAN", help_text="European Article Number")
    
    # Informazioni prodotto
    title = models.CharField(max_length=500, verbose_name="Titolo prodotto")
    brand = models.CharField(max_length=200, blank=True, null=True, verbose_name="Brand")
    condition = models.CharField(max_length=50, default='New', verbose_name="Condizione", 
                                choices=[('New', 'Nuovo'), ('Used', 'Usato'), ('Refurbished', 'Ricondizionato')])
    
    # Dimensioni e peso
    length_mm = models.PositiveIntegerField(blank=True, null=True, verbose_name="Lunghezza (mm)")
    width_mm = models.PositiveIntegerField(blank=True, null=True, verbose_name="Larghezza (mm)")
    height_mm = models.PositiveIntegerField(blank=True, null=True, verbose_name="Altezza (mm)")
    weight_gm = models.PositiveIntegerField(blank=True, null=True, verbose_name="Peso (g)")
    
    # Inventario e soglie
    current_stock = models.PositiveIntegerField(default=0, verbose_name="Stock attuale")
    minimum_stock = models.PositiveIntegerField(default=0, verbose_name="Stock minimo", 
                                               help_text="Soglia sotto la quale si considera necessario il rifornimento")
    optimal_stock = models.PositiveIntegerField(default=0, verbose_name="Stock ottimale",
                                               help_text="Quantità ideale da mantenere in magazzino")
    
    # Informazioni costi e vendite
    cost_per_unit = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, 
                                       verbose_name="Costo unitario")
    sales_velocity = models.DecimalField(max_digits=8, decimal_places=2, default=0, 
                                        verbose_name="Velocità vendite (unità/mese)")
    
    # Metadati
    is_active = models.BooleanField(default=True, verbose_name="Attivo")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creato il")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Aggiornato il")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Creato da")
    
    # Note
    notes = models.TextField(blank=True, null=True, verbose_name="Note")
    
    class Meta:
        verbose_name = "Prodotto"
        verbose_name_plural = "Prodotti"
        ordering = ['brand', 'title']
        indexes = [
            models.Index(fields=['sku']),
            models.Index(fields=['asin']),
            models.Index(fields=['brand']),
            models.Index(fields=['is_active', '-updated_at']),
            models.Index(fields=['current_stock']),
        ]
    
    def __str__(self):
        return f"{self.sku} - {self.title}"
    
    @property
    def needs_restocking(self):
        """Indica se il prodotto ha bisogno di rifornimento"""
        return self.current_stock <= self.minimum_stock
    
    @property
    def suggested_order_quantity(self):
        """Calcola la quantità suggerita per l'ordine"""
        if self.optimal_stock > self.current_stock:
            return self.optimal_stock - self.current_stock
        return 0
    
    @property
    def days_of_inventory(self):
        """Calcola i giorni di copertura dell'inventario attuale"""
        if self.sales_velocity > 0:
            monthly_velocity = float(self.sales_velocity)
            daily_velocity = monthly_velocity / 30
            return round(self.current_stock / daily_velocity, 1)
        return 0


class RifornimentoRequest(models.Model):
    """
    Modello per le richieste di rifornimento
    """
    STATUS_CHOICES = [
        ('draft', 'Bozza'),
        ('pending', 'In attesa'),
        ('approved', 'Approvata'),
        ('ordered', 'Ordinata'),
        ('shipped', 'Spedita'),
        ('received', 'Ricevuta'),
        ('cancelled', 'Annullata'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Bassa'),
        ('normal', 'Normale'),
        ('high', 'Alta'),
        ('urgent', 'Urgente'),
    ]
    
    # Identificatori
    request_number = models.CharField(max_length=50, unique=True, verbose_name="Numero richiesta",
                                     help_text="Generato automaticamente")
    title = models.CharField(max_length=200, verbose_name="Titolo richiesta")
    
    # Status e priorità
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name="Stato")
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='normal', verbose_name="Priorità")
    
    # Date importanti
    request_date = models.DateTimeField(default=timezone.now, verbose_name="Data richiesta")
    needed_by = models.DateField(blank=True, null=True, verbose_name="Necessario entro",
                                help_text="Data entro cui è necessario ricevere i prodotti")
    approved_date = models.DateTimeField(blank=True, null=True, verbose_name="Data approvazione")
    order_date = models.DateTimeField(blank=True, null=True, verbose_name="Data ordine")
    expected_delivery = models.DateField(blank=True, null=True, verbose_name="Consegna prevista")
    actual_delivery = models.DateField(blank=True, null=True, verbose_name="Consegna effettiva")
    
    # Persone coinvolte
    requested_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='rifornimento_requests',
                                    verbose_name="Richiesto da")
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='approved_rifornimenti', verbose_name="Approvato da")
    
    # Informazioni fornitore
    supplier = models.CharField(max_length=200, blank=True, null=True, verbose_name="Fornitore")
    supplier_reference = models.CharField(max_length=100, blank=True, null=True, 
                                         verbose_name="Riferimento fornitore")
    
    # Costi totali
    total_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Costo totale")
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Costo spedizione")
    
    # Note e documenti
    notes = models.TextField(blank=True, null=True, verbose_name="Note")
    internal_notes = models.TextField(blank=True, null=True, verbose_name="Note interne")
    
    # Metadati
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creato il")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Aggiornato il")
    
    class Meta:
        verbose_name = "Richiesta di Rifornimento"
        verbose_name_plural = "Richieste di Rifornimento"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['priority', '-created_at']),
            models.Index(fields=['requested_by', '-created_at']),
            models.Index(fields=['request_number']),
        ]
    
    def __str__(self):
        return f"{self.request_number} - {self.title}"
    
    def save(self, *args, **kwargs):
        # Genera numero richiesta automaticamente
        if not self.request_number:
            last_request = RifornimentoRequest.objects.filter(
                request_number__startswith='RIF'
            ).order_by('-request_number').first()
            
            if last_request:
                last_number = int(last_request.request_number[3:])
                new_number = last_number + 1
            else:
                new_number = 1
            
            self.request_number = f"RIF{new_number:06d}"
        
        super().save(*args, **kwargs)
    
    @property
    def total_items(self):
        """Numero totale di tipologie di prodotti nella richiesta"""
        return self.items.count()
    
    @property
    def total_quantity(self):
        """Quantità totale di tutti i prodotti nella richiesta"""
        return sum(item.quantity for item in self.items.all())
    
    @property
    def is_overdue(self):
        """Indica se la richiesta è in ritardo"""
        if self.needed_by and self.status not in ['received', 'cancelled']:
            return timezone.now().date() > self.needed_by
        return False


class RifornimentoItem(models.Model):
    """
    Modello per i singoli elementi di una richiesta di rifornimento
    """
    # Relazioni
    request = models.ForeignKey(RifornimentoRequest, on_delete=models.CASCADE, related_name='items',
                               verbose_name="Richiesta")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='rifornimento_items',
                               verbose_name="Prodotto")
    
    # Quantità
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)], verbose_name="Quantità richiesta")
    quantity_approved = models.PositiveIntegerField(blank=True, null=True, verbose_name="Quantità approvata")
    quantity_ordered = models.PositiveIntegerField(blank=True, null=True, verbose_name="Quantità ordinata")
    quantity_received = models.PositiveIntegerField(default=0, verbose_name="Quantità ricevuta")
    
    # Costi
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True,
                                   verbose_name="Costo unitario")
    total_cost = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True,
                                    verbose_name="Costo totale")
    
    # Motivazione e priorità
    reason = models.TextField(blank=True, null=True, verbose_name="Motivazione richiesta")
    priority_notes = models.TextField(blank=True, null=True, verbose_name="Note priorità")
    
    # Metadati
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creato il")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Aggiornato il")
    
    class Meta:
        verbose_name = "Elemento Rifornimento"
        verbose_name_plural = "Elementi Rifornimento"
        ordering = ['request', 'product']
        unique_together = ['request', 'product']  # Un prodotto per richiesta
        indexes = [
            models.Index(fields=['request', 'product']),
            models.Index(fields=['product', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.request.request_number} - {self.product.sku} (Qty: {self.quantity})"
    
    def save(self, *args, **kwargs):
        # Calcola costo totale se unit_cost è specificato
        if self.unit_cost and self.quantity:
            self.total_cost = self.unit_cost * self.quantity
        super().save(*args, **kwargs)
    
    @property
    def quantity_pending(self):
        """Quantità ancora da ricevere"""
        ordered = self.quantity_ordered or self.quantity_approved or self.quantity
        return max(0, ordered - self.quantity_received)
    
    @property
    def is_fully_received(self):
        """Indica se l'elemento è stato completamente ricevuto"""
        ordered = self.quantity_ordered or self.quantity_approved or self.quantity
        return self.quantity_received >= ordered
