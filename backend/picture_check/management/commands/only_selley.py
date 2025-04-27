from django.core.management.base import BaseCommand
from picture_check.models import Cliente

class Command(BaseCommand):
    help = 'Cancella tutti i clienti e inserisce solo Selley'

    def handle(self, *args, **kwargs):
        Cliente.objects.all().delete()
        Cliente.objects.create(nome="Selley", attivo=True)
        self.stdout.write(self.style.SUCCESS('Tabella clienti aggiornata: solo Selley presente.'))