from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('prep_management', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ShipmentStatusUpdate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('shipment_id', models.CharField(max_length=100, verbose_name='ID Spedizione')),
                ('previous_status', models.CharField(blank=True, choices=[('pending', 'In attesa'), ('processing', 'In elaborazione'), ('ready', 'Pronto'), ('shipped', 'Spedito'), ('delivered', 'Consegnato'), ('cancelled', 'Annullato'), ('failed', 'Fallito'), ('returned', 'Restituito'), ('other', 'Altro')], max_length=50, null=True, verbose_name='Stato precedente')),
                ('new_status', models.CharField(choices=[('pending', 'In attesa'), ('processing', 'In elaborazione'), ('ready', 'Pronto'), ('shipped', 'Spedito'), ('delivered', 'Consegnato'), ('cancelled', 'Annullato'), ('failed', 'Fallito'), ('returned', 'Restituito'), ('other', 'Altro')], max_length=50, verbose_name='Nuovo stato')),
                ('merchant_id', models.CharField(blank=True, max_length=100, null=True, verbose_name='ID Merchant')),
                ('merchant_name', models.CharField(blank=True, max_length=255, null=True, verbose_name='Nome Merchant')),
                ('tracking_number', models.CharField(blank=True, max_length=100, null=True, verbose_name='Numero tracciamento')),
                ('carrier', models.CharField(blank=True, max_length=100, null=True, verbose_name='Corriere')),
                ('payload', models.JSONField(blank=True, null=True, verbose_name='Payload completo')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Data ricezione')),
                ('processed', models.BooleanField(default=False, verbose_name='Elaborato')),
            ],
            options={
                'verbose_name': 'Aggiornamento stato spedizione',
                'verbose_name_plural': 'Aggiornamenti stato spedizioni',
                'ordering': ['-created_at'],
            },
        ),
    ] 