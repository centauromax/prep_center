# Generated manually for pallet_label app

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PalletLabel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Data creazione')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Ultimo aggiornamento')),
                ('pallet_id', models.CharField(help_text='Identificativo univoco del pallet', max_length=100, verbose_name='ID Pallet')),
                ('sender_name', models.CharField(max_length=200, verbose_name='Nome mittente')),
                ('sender_address_line1', models.CharField(max_length=200, verbose_name='Indirizzo mittente (riga 1)')),
                ('sender_address_line2', models.CharField(blank=True, max_length=200, verbose_name='Indirizzo mittente (riga 2)')),
                ('sender_city', models.CharField(max_length=100, verbose_name='Città mittente')),
                ('sender_postal_code', models.CharField(max_length=20, verbose_name='CAP mittente')),
                ('sender_country', models.CharField(default='Italia', max_length=100, verbose_name='Paese mittente')),
                ('amazon_warehouse_code', models.CharField(help_text='Es: MXP5, LIN1, etc.', max_length=10, verbose_name='Codice warehouse Amazon')),
                ('amazon_warehouse_name', models.CharField(max_length=200, verbose_name='Nome warehouse Amazon')),
                ('amazon_address_line1', models.CharField(max_length=200, verbose_name='Indirizzo Amazon (riga 1)')),
                ('amazon_address_line2', models.CharField(blank=True, max_length=200, verbose_name='Indirizzo Amazon (riga 2)')),
                ('amazon_city', models.CharField(max_length=100, verbose_name='Città Amazon')),
                ('amazon_postal_code', models.CharField(max_length=20, verbose_name='CAP Amazon')),
                ('amazon_country', models.CharField(default='Italia', max_length=100, verbose_name='Paese Amazon')),
                ('shipment_id', models.CharField(help_text='Shipment ID di Amazon', max_length=100, verbose_name='ID Spedizione')),
                ('po_number', models.CharField(blank=True, help_text='Purchase Order Number', max_length=100, verbose_name='Numero PO')),
                ('pallet_count', models.PositiveIntegerField(default=1, verbose_name='Numero di pallet')),
                ('pallet_number', models.PositiveIntegerField(default=1, help_text='Es: 1 di 3', verbose_name='Numero pallet corrente')),
                ('total_boxes', models.PositiveIntegerField(verbose_name='Numero totale scatole')),
                ('pallet_weight', models.DecimalField(decimal_places=2, max_digits=8, verbose_name='Peso pallet (kg)')),
                ('pallet_dimensions_length', models.DecimalField(decimal_places=2, max_digits=6, verbose_name='Lunghezza (cm)')),
                ('pallet_dimensions_width', models.DecimalField(decimal_places=2, max_digits=6, verbose_name='Larghezza (cm)')),
                ('pallet_dimensions_height', models.DecimalField(decimal_places=2, max_digits=6, verbose_name='Altezza (cm)')),
                ('carrier', models.CharField(blank=True, help_text='Nome del corriere', max_length=100, verbose_name='Corriere')),
                ('tracking_number', models.CharField(blank=True, max_length=100, verbose_name='Numero di tracking')),
                ('special_instructions', models.TextField(blank=True, verbose_name='Istruzioni speciali')),
                ('pdf_generated', models.BooleanField(default=False, verbose_name='PDF generato')),
                ('pdf_file', models.FileField(blank=True, null=True, upload_to='pallet_labels/', verbose_name='File PDF')),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='Creato da')),
            ],
            options={
                'verbose_name': 'Etichetta Pallet',
                'verbose_name_plural': 'Etichette Pallet',
                'ordering': ['-created_at'],
            },
        ),
    ] 