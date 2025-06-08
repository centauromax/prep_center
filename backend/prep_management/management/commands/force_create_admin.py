from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
import os


class Command(BaseCommand):
    help = 'Forza la creazione/aggiornamento del superuser admin'

    def handle(self, *args, **options):
        username = 'admin'
        email = 'admin@fbaprepcenteritaly.com'
        password = 'FbaPrepAdmin2024!'

        # Elimina l'utente se esiste
        User.objects.filter(username=username).delete()
        
        # Crea nuovo superuser
        user = User.objects.create_superuser(
            username=username,
            email=email,
            password=password
        )
        
        self.stdout.write(
            self.style.SUCCESS(f'✅ Superuser "{username}" creato/aggiornato con successo!')
        )
        self.stdout.write(
            self.style.WARNING(f'📧 Email: {email}')
        )
        self.stdout.write(
            self.style.WARNING(f'🔑 Password: {password}')
        )
        self.stdout.write(
            self.style.SUCCESS(f'🆔 User ID: {user.id}')
        ) 