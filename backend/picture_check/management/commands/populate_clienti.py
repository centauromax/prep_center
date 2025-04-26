from django.core.management.base import BaseCommand
from picture_check.models import Cliente
import logging

logger = logging.getLogger('picture_check')

class Command(BaseCommand):
    help = 'Popola il database con clienti di esempio per l\'app Picture Check'

    def handle(self, *args, **kwargs):
        clienti_esempio = [
            "Amazon",
            "Ebay",
            "Shein",
            "AliExpress",
            "Walmart",
            "MercadoLibre",
            "Shopify",
            "Allegro",
            "Privato",
            "Altro"
        ]

        counter = 0
        for nome_cliente in clienti_esempio:
            cliente, creato = Cliente.objects.get_or_create(nome=nome_cliente)
            if creato:
                counter += 1
                self.stdout.write(self.style.SUCCESS(f'Cliente "{nome_cliente}" creato con successo.'))
            else:
                self.stdout.write(self.style.WARNING(f'Cliente "{nome_cliente}" già esistente.'))

        self.stdout.write(self.style.SUCCESS(f'Completato. Creati {counter} nuovi clienti di esempio.')) 