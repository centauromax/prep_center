# Generated manually for pallet_label.0003_add_lingua_etichette

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pallet_label', '0002_new_pallet_structure'),
    ]

    operations = [
        migrations.AddField(
            model_name='palletlabel',
            name='lingua_etichette',
            field=models.CharField(
                choices=[('it', 'Italiano'), ('fr', 'Francese'), ('de', 'Tedesco'), ('es', 'Spagnolo')],
                default='it',
                max_length=2,
                verbose_name='Lingua etichette'
            ),
        ),
    ] 