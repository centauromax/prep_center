from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('api/open-shipments/', views.open_shipments, name='open_shipments'),
    path('merchants/', views.merchants_list, name='merchants_list'),
]
