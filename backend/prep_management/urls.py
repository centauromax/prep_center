from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('api/open-shipments/', views.open_shipments, name='open_shipments'),
    path('merchants/', views.merchants_list, name='merchants_list'),
    path('api-debug/', views.api_config_debug, name='api_config_debug'),
    path('webhook/', views.shipment_status_webhook, name='shipment_status_webhook'),
    path('webhook/test/', views.test_webhook, name='test_webhook'),
    path('shipment-updates/', views.shipment_status_updates, name='shipment_status_updates'),
    path('webhook/manage/', views.manage_webhooks, name='manage_webhooks'),
    path('queue/push/', views.push_outgoing_message, name='push_outgoing_message'),
    path('queue/poll/', views.poll_outgoing_messages, name='poll_outgoing_messages'),
    path('queue/consume/<int:pk>/', views.push_outgoing_message, name='consume_outgoing_message'),
]
