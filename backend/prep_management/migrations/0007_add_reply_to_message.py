# Generated manually for adding reply_to_message field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('prep_management', '0006_add_chat_system'),
    ]

    operations = [
        migrations.AddField(
            model_name='telegramchatmessage',
            name='reply_to_message',
            field=models.JSONField(
                blank=True,
                help_text='Informazioni del messaggio originale a cui si sta rispondendo',
                null=True,
                verbose_name='Risposta a messaggio'
            ),
        ),
    ] 