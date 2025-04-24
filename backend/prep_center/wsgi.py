"""
WSGI config for prep_center project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application
from django.conf import settings # Import settings
from whitenoise import WhiteNoise # Import WhiteNoise

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'prep_center.settings')

# Ottieni l'applicazione WSGI standard
application = get_wsgi_application()

# Applica WhiteNoise specificando la STATIC_ROOT
# Assicurati che settings.STATIC_ROOT sia definito correttamente
if hasattr(settings, 'STATIC_ROOT') and settings.STATIC_ROOT:
    application = WhiteNoise(application, root=settings.STATIC_ROOT)
    # Aggiungi anche i file da STATICFILES_DIRS se necessario (generalmente non serve se collectstatic funziona)
    # if hasattr(settings, 'STATICFILES_DIRS'):
    #     for directory in settings.STATICFILES_DIRS:
    #         application.add_files(directory)
else:
    # Fallback o log se STATIC_ROOT non è definito
    print("WARNING: settings.STATIC_ROOT not defined, WhiteNoise not fully configured.")
