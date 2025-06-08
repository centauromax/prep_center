# Generated manually to update email field labels
# Generated on 2025-01-11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('prep_management', '0012_allow_multiple_users_per_email'),
    ]

    operations = [
        migrations.AlterField(
            model_name='telegramnotification',
            name='email',
            field=models.EmailField(
                help_text='Email utilizzata nell\'account del cliente sul software del Prep Center',
                verbose_name='Email Prep Center'
            ),
        ),
    ] 