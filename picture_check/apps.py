from django.apps import AppConfig


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
        pass 