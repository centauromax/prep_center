from django.urls import path
from . import views

app_name = 'rifornimento'

urlpatterns = [
    # Dashboard e viste principali
    path('', views.dashboard, name='dashboard'),
    path('dashboard/', views.dashboard, name='dashboard_alt'),
    
    # Gestione prodotti
    path('products/', views.product_list, name='product_list'),
    
    # Gestione richieste rifornimento
    path('requests/', views.request_list, name='request_list'),
    path('requests/<int:request_id>/', views.request_detail, name='request_detail'),
    
    # API Endpoints
    path('api/dashboard/stats/', views.api_dashboard_stats, name='api_dashboard_stats'),
    path('api/products/low-stock/', views.api_products_low_stock, name='api_products_low_stock'),
    path('api/requests/create-from-products/', views.api_create_request_from_products, name='api_create_request_from_products'),
] 