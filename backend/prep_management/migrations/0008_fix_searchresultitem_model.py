# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('prep_management', '0007_searchresultitem_processing_status_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='searchresultitem',
            name='shipment_id_api',
            field=models.CharField(max_length=36),
        ),
        migrations.AddField(
            model_name='searchresultitem',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
    ] 