# Generated manually for Telegram models
# Generated on 2025-01-11

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('prep_management', '0010_merge_20250529_1620'),
    ]

    operations = [
        migrations.CreateModel(
            name='TelegramNotification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email', models.EmailField(help_text='Email utilizzata nell\'account PrepBusiness del cliente', max_length=254, unique=True, verbose_name='Email PrepBusiness')),
                ('chat_id', models.BigIntegerField(help_text='ID della chat Telegram per l\'invio di notifiche', unique=True, verbose_name='Chat ID Telegram')),
                ('username', models.CharField(blank=True, max_length=100, null=True, verbose_name='Username Telegram')),
                ('first_name', models.CharField(blank=True, max_length=100, null=True, verbose_name='Nome')),
                ('last_name', models.CharField(blank=True, max_length=100, null=True, verbose_name='Cognome')),
                ('is_active', models.BooleanField(default=True, help_text='Se disattivato, non riceverà notifiche', verbose_name='Attivo')),
                ('language_code', models.CharField(blank=True, default='it', max_length=10, null=True, verbose_name='Codice lingua')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Data registrazione')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Ultimo aggiornamento')),
                ('last_notification_at', models.DateTimeField(blank=True, null=True, verbose_name='Ultima notifica')),
                ('total_notifications_sent', models.PositiveIntegerField(default=0, verbose_name='Notifiche inviate')),
            ],
            options={
                'verbose_name': 'Notifica Telegram',
                'verbose_name_plural': 'Notifiche Telegram',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='TelegramMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('message_text', models.TextField(verbose_name='Testo messaggio')),
                ('status', models.CharField(choices=[('pending', 'In attesa'), ('sent', 'Inviato'), ('failed', 'Fallito'), ('retry', 'Da riprovare')], default='pending', max_length=20, verbose_name='Stato')),
                ('telegram_message_id', models.BigIntegerField(blank=True, null=True, verbose_name='ID Messaggio Telegram')),
                ('error_message', models.TextField(blank=True, null=True, verbose_name='Messaggio errore')),
                ('retry_count', models.PositiveIntegerField(default=0, verbose_name='Tentativi')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Data creazione')),
                ('sent_at', models.DateTimeField(blank=True, null=True, verbose_name='Data invio')),
                ('event_type', models.CharField(blank=True, help_text='Tipo di evento che ha generato il messaggio', max_length=100, null=True, verbose_name='Tipo evento')),
                ('shipment_id', models.CharField(blank=True, max_length=100, null=True, verbose_name='ID Spedizione')),
                ('telegram_user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='prep_management.telegramnotification', verbose_name='Utente Telegram')),
            ],
            options={
                'verbose_name': 'Messaggio Telegram',
                'verbose_name_plural': 'Messaggi Telegram',
                'ordering': ['-created_at'],
            },
        ),
    ] 