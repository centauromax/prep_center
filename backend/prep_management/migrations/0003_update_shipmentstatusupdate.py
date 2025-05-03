from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('prep_management', '0002_shipmentstatusupdate'),
    ]

    operations = [
        migrations.AddField(
            model_name='shipmentstatusupdate',
            name='event_type',
            field=models.CharField(choices=[('inbound_shipment.created', 'Spedizione in entrata creata'), ('inbound_shipment.notes_updated', 'Note spedizione in entrata aggiornate'), ('inbound_shipment.shipped', 'Spedizione in entrata spedita'), ('inbound_shipment.received', 'Spedizione in entrata ricevuta'), ('outbound_shipment.created', 'Spedizione in uscita creata'), ('outbound_shipment.shipped', 'Spedizione in uscita spedita'), ('outbound_shipment.notes_updated', 'Note spedizione in uscita aggiornate'), ('outbound_shipment.closed', 'Spedizione in uscita chiusa'), ('order.created', 'Ordine creato'), ('order.shipped', 'Ordine spedito'), ('invoice.created', 'Fattura creata'), ('other', 'Altro')], default='other', max_length=100, verbose_name='Tipo evento'),
        ),
        migrations.AddField(
            model_name='shipmentstatusupdate',
            name='entity_type',
            field=models.CharField(blank=True, help_text='Tipo di entità (inbound_shipment, outbound_shipment, order, invoice)', max_length=50, null=True, verbose_name='Tipo entità'),
        ),
        migrations.AddField(
            model_name='shipmentstatusupdate',
            name='notes',
            field=models.TextField(blank=True, null=True, verbose_name='Note'),
        ),
        migrations.AlterField(
            model_name='shipmentstatusupdate',
            name='new_status',
            field=models.CharField(choices=[('pending', 'In attesa'), ('processing', 'In elaborazione'), ('ready', 'Pronto'), ('shipped', 'Spedito'), ('delivered', 'Consegnato'), ('cancelled', 'Annullato'), ('failed', 'Fallito'), ('returned', 'Restituito'), ('created', 'Creato'), ('received', 'Ricevuto'), ('notes_updated', 'Note aggiornate'), ('closed', 'Chiuso'), ('other', 'Altro')], max_length=50, verbose_name='Nuovo stato'),
        ),
        migrations.AlterField(
            model_name='shipmentstatusupdate',
            name='previous_status',
            field=models.CharField(blank=True, choices=[('pending', 'In attesa'), ('processing', 'In elaborazione'), ('ready', 'Pronto'), ('shipped', 'Spedito'), ('delivered', 'Consegnato'), ('cancelled', 'Annullato'), ('failed', 'Fallito'), ('returned', 'Restituito'), ('created', 'Creato'), ('received', 'Ricevuto'), ('notes_updated', 'Note aggiornate'), ('closed', 'Chiuso'), ('other', 'Altro')], max_length=50, null=True, verbose_name='Stato precedente'),
        ),
    ] 