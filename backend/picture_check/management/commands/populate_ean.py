from django.core.management.base import BaseCommand
from picture_check.models import PictureCheck, Cliente
from django.utils import timezone
import random

class Command(BaseCommand):
    help = 'Popola il database con EAN di test per Picture Check'

    def handle(self, *args, **kwargs):
        clienti = list(Cliente.objects.all())
        if not clienti:
            self.stdout.write(self.style.ERROR('Nessun cliente trovato. Popola prima i clienti!'))
            return

        ean_base = 8000000000000
        ean_list = [str(ean_base + i) for i in range(1, 21)]
        counter = 0
        for ean in ean_list:
            cliente = random.choice(clienti)
            obj, created = PictureCheck.objects.get_or_create(
                ean=ean,
                cliente=cliente.nome,
                defaults={"data": timezone.now().date()}
            )
            if created:
                counter += 1
                self.stdout.write(self.style.SUCCESS(f'Creato EAN {ean} per cliente {cliente.nome}'))
            else:
                self.stdout.write(self.style.WARNING(f'EAN {ean} già presente per cliente {cliente.nome}'))
        self.stdout.write(self.style.SUCCESS(f'Completato. Creati {counter} nuovi EAN di test.')) 