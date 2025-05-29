# Generated manually to merge conflicting migrations

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('prep_management', '0008_incomingmessage'),
        ('prep_management', '0009_remove_shipment_id_api'),
    ]

    operations = [
        # No operations needed - this is just a merge migration
    ] 