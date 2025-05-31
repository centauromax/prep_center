# Generated manually on 2025-01-17 14:00

from django.conf import settings
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('pallet_label', '0001_initial'),
    ]

    operations = [
        # Elimina il modello vecchio
        migrations.DeleteModel(
            name='PalletLabel',
        ),
        
        # Crea il nuovo modello
        migrations.CreateModel(
            name='PalletLabel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Creato il')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Aggiornato il')),
                ('nome_venditore', models.CharField(max_length=200, verbose_name='Nome del venditore')),
                ('nome_spedizione', models.CharField(max_length=500, verbose_name='Nome spedizione')),
                ('numero_spedizione', models.CharField(max_length=100, verbose_name='Numero spedizione')),
                ('indirizzo_spedizione', models.TextField(verbose_name='Indirizzo di spedizione')),
                ('pallet_numero', models.PositiveIntegerField(validators=[django.core.validators.MinValueValidator(1)], verbose_name='Numero pallet corrente')),
                ('pallet_totale', models.PositiveIntegerField(validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(50)], verbose_name='Numero totale pallet')),
                ('numero_cartoni', models.PositiveIntegerField(validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(1000)], verbose_name='Numero di cartoni in questo pallet')),
                ('origine_spedizione', models.TextField(default='FBAPREPCENTER, Via Caorliega 37, Mirano, Venezia, 30035, IT', verbose_name='Indirizzo di origine')),
                ('pdf_generated', models.BooleanField(default=False, verbose_name='PDF generato')),
                ('pdf_file', models.FileField(blank=True, null=True, upload_to='pallet_labels/', verbose_name='File PDF')),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='Creato da')),
            ],
            options={
                'verbose_name': 'Etichetta Pallet',
                'verbose_name_plural': 'Etichette Pallet',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['created_by', '-created_at'], name='pallet_labe_created_aa2b08_idx'),
                    models.Index(fields=['numero_spedizione'], name='pallet_labe_numero__7a4829_idx'),
                    models.Index(fields=['nome_venditore'], name='pallet_labe_nome_ve_ad8b91_idx'),
                ],
            },
        ),
    ] 