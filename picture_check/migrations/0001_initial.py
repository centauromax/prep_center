from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Cliente',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=100, verbose_name='Nome Cliente')),
                ('attivo', models.BooleanField(default=True, verbose_name='Cliente Attivo')),
            ],
            options={
                'verbose_name': 'Cliente',
                'verbose_name_plural': 'Clienti',
                'ordering': ['nome'],
            },
        ),
        migrations.CreateModel(
            name='PictureCheck',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('data', models.DateField(auto_now_add=True, verbose_name='Data Verifica')),
                ('ean', models.CharField(db_index=True, max_length=20, verbose_name='Codice EAN')),
                ('cliente', models.CharField(max_length=100, verbose_name='Cliente')),
            ],
            options={
                'verbose_name': 'Verifica Foto',
                'verbose_name_plural': 'Verifiche Foto',
                'ordering': ['-data', 'cliente'],
            },
        ),
    ] 