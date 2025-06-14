"""
WSGI config for prep_center project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/wsgi/
"""

import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'prep_center.settings')

application = get_wsgi_application()

# Scrivi la versione corrente in un file all'avvio
try:
    from django.conf import settings
    version = getattr(settings, 'VERSION', 'unknown')
    version_file_path = '/tmp/prep_center_version.txt'
    
    with open(version_file_path, 'w') as f:
        f.write(version)
    
    print(f"[WSGI] Prep Center versione {version} avviata - file versione scritto in {version_file_path}")
except Exception as e:
    print(f"[WSGI] Errore nella scrittura del file versione: {e}")
