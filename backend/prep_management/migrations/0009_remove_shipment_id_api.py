from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('prep_management', '0007_searchresultitem_processing_status_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='searchresultitem',
            name='shipment_id_api',
        ),
    ] 