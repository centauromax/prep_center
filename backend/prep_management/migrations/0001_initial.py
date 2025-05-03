from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='PrepBusinessConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('api_url', models.URLField(default='https://dashboard.fbaprepcenteritaly.com/api', max_length=255, verbose_name='URL API')),
                ('api_key', models.CharField(max_length=255, verbose_name='API Key')),
                ('api_timeout', models.PositiveIntegerField(default=30, verbose_name='Timeout (secondi)')),
                ('max_retries', models.PositiveIntegerField(default=3, verbose_name='Tentativi massimi')),
                ('retry_backoff', models.FloatField(default=0.5, verbose_name='Backoff (secondi)')),
                ('is_active', models.BooleanField(default=True, verbose_name='Attivo')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Data creazione')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Ultimo aggiornamento')),
            ],
            options={
                'verbose_name': 'Configurazione Prep Business',
                'verbose_name_plural': 'Configurazioni Prep Business',
            },
        ),
    ] 