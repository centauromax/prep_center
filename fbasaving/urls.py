# /var/www/html/webapps/projects/prep_center/fbasaving/urls.py

from django.urls import path
from . import views
from django.views.i18n import JavaScriptCatalog

app_name = 'fbasaving'

urlpatterns = [
    path('', views.home, name='home'),
    path('upload/', views.upload_file_view, name='upload_file'),
    path('data/', views.data_tables_view, name='data_tables'),
    path('jsi18n/', JavaScriptCatalog.as_view(), name='js_catalog'),
    path('contact/', views.contact, name='contact'),
]
