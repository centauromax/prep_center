from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ('prep_management', '0017_alter_shipmentstatusupdate_unique_together'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='shipmentstatusupdate',
            unique_together=set(),
        ),
    ] 