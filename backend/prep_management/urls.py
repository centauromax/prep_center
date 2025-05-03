from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('api/open-shipments/', views.open_shipments, name='open_shipments'),
    path('merchants/', views.merchants_list, name='merchants_list'),
    path('api-debug/', views.api_config_debug, name='api_config_debug'),
    path('webhook/shipment-status/', views.shipment_status_webhook, name='shipment_status_webhook'),
    path('shipment-updates/', views.shipment_status_updates, name='shipment_status_updates'),
]
