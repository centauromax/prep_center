from django.db import models

# Create your models here. 

class PictureCheck(models.Model):
    """
    Modello per salvare gli EAN verificati per cui le foto non sono state ancora fatte
    """
    data = models.DateField(verbose_name="Data Verifica")
    ean = models.CharField(max_length=20, verbose_name="Codice EAN", db_index=True)
    cliente = models.CharField(max_length=100, verbose_name="Cliente")
    
    class Meta:
        verbose_name = "Verifica Foto"
        verbose_name_plural = "Verifiche Foto"
        ordering = ['-data', 'cliente']
    
    def __str__(self):
        return f"{self.ean} - {self.cliente} ({self.data})"

class Cliente(models.Model):
    """
    Modello per la gestione dei clienti
    """
    nome = models.CharField(max_length=100, verbose_name="Nome Cliente")
    attivo = models.BooleanField(default=True, verbose_name="Cliente Attivo")
    
    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clienti"
        ordering = ['nome']
    
    def __str__(self):
        return self.nome 