from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator


class PalletLabel(models.Model):
    """
    Modello per memorizzare le etichette pallet secondo i nuovi requisiti.
    """
    # Metadati
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Creato da")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creato il")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Aggiornato il")
    
    # Dati della spedizione (parte superiore dell'etichetta - uguale per tutti i pallet)
    nome_venditore = models.CharField(max_length=200, verbose_name="Nome del venditore")
    nome_spedizione = models.CharField(max_length=500, verbose_name="Nome spedizione")
    numero_spedizione = models.CharField(max_length=100, verbose_name="Numero spedizione")
    indirizzo_spedizione = models.TextField(verbose_name="Indirizzo di spedizione")
    
    # Dati del pallet specifico (parte inferiore dell'etichetta - varia per ogni pallet)
    pallet_numero = models.PositiveIntegerField(
        verbose_name="Numero pallet corrente",
        validators=[MinValueValidator(1)]
    )
    pallet_totale = models.PositiveIntegerField(
        verbose_name="Numero totale pallet",
        validators=[MinValueValidator(1), MaxValueValidator(50)]
    )
    numero_cartoni = models.PositiveIntegerField(
        verbose_name="Numero di cartoni in questo pallet",
        validators=[MinValueValidator(1), MaxValueValidator(1000)]
    )
    
    # Indirizzo di origine (fisso per tutte le etichette)
    origine_spedizione = models.TextField(
        default="FBAPREPCENTER, Via Caorliega 37, Mirano, Venezia, 30035, IT",
        verbose_name="Indirizzo di origine"
    )
    
    # File PDF generato
    pdf_generated = models.BooleanField(default=False, verbose_name="PDF generato")
    pdf_file = models.FileField(
        upload_to='pallet_labels/',
        null=True,
        blank=True,
        verbose_name="File PDF"
    )
    
    class Meta:
        verbose_name = "Etichetta Pallet"
        verbose_name_plural = "Etichette Pallet"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_by', '-created_at']),
            models.Index(fields=['numero_spedizione']),
            models.Index(fields=['nome_venditore']),
        ]
    
    def __str__(self):
        return f"Pallet {self.pallet_numero}/{self.pallet_totale} - {self.nome_venditore} - {self.numero_spedizione}"
    
    def get_pallet_display(self):
        """Restituisce la stringa 'Pallet n. X di Y'"""
        return f"Pallet n. {self.pallet_numero} di {self.pallet_totale}"
    
    @property
    def pdf_filename(self):
        """Genera il nome del file PDF per l'intera spedizione"""
        return f"etichette_spedizione_{self.numero_spedizione}.pdf"
