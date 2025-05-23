# Generated by Django 4.2.16 on 2025-05-06 18:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('prep_management', '0004_add_processing_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='OutgoingMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('message_id', models.CharField(choices=[('OUTBOUND_WITHOUT_INBOUND', 'Outbound without inbound')], max_length=100, verbose_name='Tipo messaggio')),
                ('parameters', models.JSONField(blank=True, null=True, verbose_name='Parametri messaggio')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Data creazione')),
                ('consumed', models.BooleanField(default=False, verbose_name='Consumto')),
                ('consumed_at', models.DateTimeField(blank=True, null=True, verbose_name='Data consumo')),
            ],
            options={
                'verbose_name': 'Messaggio in coda',
                'verbose_name_plural': 'Messaggi in coda',
            },
        ),
    ]
