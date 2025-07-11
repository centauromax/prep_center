# Generated by Django 4.2.13 on 2025-06-13 07:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('prep_management', '0015_add_reply_to_message'),
    ]

    operations = [
        migrations.AlterField(
            model_name='outgoingmessage',
            name='message_id',
            field=models.CharField(choices=[('OUTBOUND_WITHOUT_INBOUND', 'Outbound without inbound'), ('BOX_SERVICES_REQUEST', 'Box Services Request'), ('RESIDUAL_INBOUND_ERROR', 'Residual Inbound Error')], max_length=100, verbose_name='Tipo messaggio'),
        ),
        migrations.AddConstraint(
            model_name='shipmentstatusupdate',
            constraint=models.UniqueConstraint(fields=('shipment_id', 'event_type', 'new_status', 'merchant_id'), name='unique_webhook_per_shipment_event', violation_error_message='Webhook duplicato: stesso shipment_id, event_type e status già presente'),
        ),
    ]
