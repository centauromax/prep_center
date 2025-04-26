from django.apps import AppConfig


class PictureCheckConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'picture_check'
    verbose_name = 'Controllo Foto'
    
    def ready(self):
        pass 