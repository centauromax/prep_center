# Generated manually for multiple users per email support
# Generated on 2025-01-11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('prep_management', '0011_telegram_models'),
    ]

    operations = [
        # Rimuove il constraint unique dall'email
        migrations.AlterField(
            model_name='telegramnotification',
            name='email',
            field=models.EmailField(
                help_text='Email utilizzata nell\'account PrepBusiness del cliente',
                verbose_name='Email PrepBusiness'
            ),
        ),
        # Aggiunge unique_together per email+chat_id
        migrations.AlterUniqueTogether(
            name='telegramnotification',
            unique_together={('email', 'chat_id')},
        ),
    ] 