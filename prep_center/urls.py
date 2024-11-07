# /var/www/html/webapps/projects/prep_center/prep_center/urls.py

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('fbasaving/', include('fbasaving.urls')),
    path('return_management/', include('return_management.urls')),
    path('i18n/', include('django.conf.urls.i18n')),
]
