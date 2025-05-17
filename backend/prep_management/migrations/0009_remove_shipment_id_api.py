from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('prep_management', '0008_fix_searchresultitem_model'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='searchresultitem',
            name='shipment_id_api',
        ),
    ] 