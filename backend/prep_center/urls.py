# /var/www/html/webapps/projects/prep_center/prep_center/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf.urls.i18n import i18n_patterns
import logging

logger = logging.getLogger('prep_center')
logger.info('[prep_center.urls] File urls.py caricato')

# URL patterns non localizzati (sempre disponibili)
logger.info('[prep_center.urls] Prima di includere prep_management.urls')
urlpatterns = [
    path('prep_management/', include('prep_management.urls')),
    path('i18n/', include('django.conf.urls.i18n')),  # Manteniamo questo fuori da i18n_patterns
]
logger.info('[prep_center.urls] Dopo aver incluso prep_management.urls')

# URL patterns localizzati
urlpatterns += i18n_patterns(
    path('admin/', admin.site.urls),
    path('fbasaving/', include('fbasaving.urls')),
    path('return_management/', include('return_management.urls')),
    path('picture_check/', include('picture_check.urls')),
    prefix_default_language=False  # Non aggiunge il prefisso della lingua di default all'URL
)
