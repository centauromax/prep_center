from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('prep_management', '0003_update_shipmentstatusupdate'),
    ]

    operations = [
        migrations.AddField(
            model_name='shipmentstatusupdate',
            name='processed',
            field=models.BooleanField(default=False, verbose_name='Elaborato'),
        ),
        migrations.AddField(
            model_name='shipmentstatusupdate',
            name='processed_at',
            field=models.DateTimeField(null=True, blank=True, verbose_name='Data elaborazione'),
        ),
        migrations.AddField(
            model_name='shipmentstatusupdate',
            name='process_success',
            field=models.BooleanField(null=True, blank=True, verbose_name='Elaborazione riuscita'),
        ),
        migrations.AddField(
            model_name='shipmentstatusupdate',
            name='process_message',
            field=models.TextField(null=True, blank=True, verbose_name='Messaggio elaborazione'),
        ),
        migrations.AddField(
            model_name='shipmentstatusupdate',
            name='process_result',
            field=models.JSONField(null=True, blank=True, verbose_name='Risultato elaborazione'),
        ),
        migrations.AddField(
            model_name='shipmentstatusupdate',
            name='related_shipment_id',
            field=models.CharField(blank=True, max_length=100, null=True, verbose_name='ID Spedizione correlata', help_text='ID di una spedizione correlata a questa (es. spedizione in entrata correlata a una in uscita)'),
        ),
    ] 