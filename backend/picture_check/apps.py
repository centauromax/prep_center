from django.apps import AppConfig
from django.db.utils import OperationalError, ProgrammingError


class PictureCheckConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'picture_check'
    verbose_name = 'Controllo Foto'
    
    def ready(self):
        """
        Chiamato quando l'app è pronta - può essere usato per registrare segnali o
        eseguire operazioni all'avvio dell'app
        """
        # Questa app è disponibile solo in italiano
        from .models import Cliente, PictureCheck
        import random
        from django.utils import timezone

        try:
            # Popola clienti se non esistono
            if Cliente.objects.count() == 0:
                clienti_esempio = [
                    "Amazon", "Ebay", "Shein", "AliExpress", "Walmart",
                    "MercadoLibre", "Shopify", "Allegro", "Privato", "Altro"
                ]
                for nome in clienti_esempio:
                    Cliente.objects.get_or_create(nome=nome)
                print("Clienti di esempio creati.")

            # Popola EAN se non esistono
            if PictureCheck.objects.count() == 0 and Cliente.objects.exists():
                clienti = list(Cliente.objects.all())
                ean_base = 8000000000000
                ean_list = [str(ean_base + i) for i in range(1, 21)]
                for ean in ean_list:
                    cliente = random.choice(clienti)
                    PictureCheck.objects.get_or_create(
                        ean=ean,
                        cliente=cliente.nome,
                        defaults={"data": timezone.now().date()}
                    )
                print("EAN di test creati.")
        except (OperationalError, ProgrammingError):
            # Il DB non è pronto (es. durante migrate)
            pass 