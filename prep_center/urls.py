# /var/www/html/webapps/projects/prep_center/prep_center/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf.urls.i18n import i18n_patterns

# URL patterns non localizzati (sempre disponibili)
urlpatterns = [
    path('i18n/', include('django.conf.urls.i18n')),  # Manteniamo questo fuori da i18n_patterns
]

# URL patterns localizzati
urlpatterns += i18n_patterns(
    path('admin/', admin.site.urls),
    path('fbasaving/', include('fbasaving.urls')),
    path('return_management/', include('return_management.urls')),
    prefix_default_language=False  # Non aggiunge il prefisso della lingua di default all'URL
)
