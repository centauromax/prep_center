from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
import os


class Command(BaseCommand):
    help = 'Crea un superuser admin se non esiste già'

    def handle(self, *args, **options):
        username = os.getenv('DJANGO_SUPERUSER_USERNAME', 'admin')
        email = os.getenv('DJANGO_SUPERUSER_EMAIL', 'admin@fbaprepcenteritaly.com')
        password = os.getenv('DJANGO_SUPERUSER_PASSWORD', 'FbaPrepAdmin2024!')

        if not User.objects.filter(username=username).exists():
            User.objects.create_superuser(
                username=username,
                email=email,
                password=password
            )
            self.stdout.write(
                self.style.SUCCESS(f'✅ Superuser "{username}" creato con successo!')
            )
            self.stdout.write(
                self.style.WARNING(f'📧 Email: {email}')
            )
            self.stdout.write(
                self.style.WARNING(f'🔑 Password: {password}')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'⚠️ Superuser "{username}" esiste già')
            ) 