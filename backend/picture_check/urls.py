from django.urls import path
from . import views

app_name = 'picture_check'

urlpatterns = [
    path('', views.home, name='home'),
    path('react/', views.react_app, name='react_app'),
    path('api/clienti/', views.get_clienti, name='get_clienti'),
    path('api/check/<str:ean>/', views.check_ean, name='check_ean'),
    path('api/salva/', views.salva_ean, name='salva_ean'),
    path('api/lista/', views.lista_ean, name='lista_ean'),
] 