"""
WSGI config for prep_center project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application
# Rimuoviamo gli import non più necessari
# from django.conf import settings
# from whitenoise import WhiteNoise

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'prep_center.settings')

application = get_wsgi_application()

# Rimuoviamo l'applicazione di WhiteNoise qui
