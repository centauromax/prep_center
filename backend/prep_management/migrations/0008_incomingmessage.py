# Generated manually for IncomingMessage model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('prep_management', '0007_searchresultitem_processing_status_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='IncomingMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('message_type', models.CharField(choices=[('USER_RESPONSE', 'Risposta utente'), ('EXTENSION_STATUS', 'Status estensione'), ('ACTION_COMPLETED', 'Azione completata'), ('ERROR_REPORT', 'Segnalazione errore')], max_length=100, verbose_name='Tipo messaggio')),
                ('payload', models.JSONField(blank=True, null=True, verbose_name='Payload messaggio')),
                ('session_id', models.CharField(blank=True, help_text='ID per correlare richiesta/risposta', max_length=100, null=True, verbose_name='ID Sessione')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Data ricezione')),
                ('processed', models.BooleanField(default=False, verbose_name='Elaborato')),
                ('processed_at', models.DateTimeField(blank=True, null=True, verbose_name='Data elaborazione')),
                ('process_result', models.JSONField(blank=True, null=True, verbose_name='Risultato elaborazione')),
            ],
            options={
                'verbose_name': 'Messaggio in entrata',
                'verbose_name_plural': 'Messaggi in entrata',
                'ordering': ['-created_at'],
            },
        ),
    ] 