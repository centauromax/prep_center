from django.urls import path
from . import views

app_name = 'pallet_label'

urlpatterns = [
    # Lista etichette
    path('', views.pallet_label_list, name='list'),
    
    # Creazione etichette
    path('create/', views.pallet_label_create, name='create'),
    path('quick-create/', views.pallet_label_quick_create, name='quick_create'),
    
    # Dettagli e gestione etichette
    path('<int:pk>/', views.pallet_label_detail, name='detail'),
    path('<int:pk>/edit/', views.pallet_label_edit, name='edit'),
    path('<int:pk>/delete/', views.pallet_label_delete, name='delete'),
    
    # Download e rigenerazione PDF
    path('<int:pk>/download/', views.pallet_label_download, name='download'),
    path('<int:pk>/regenerate-pdf/', views.pallet_label_regenerate_pdf, name='regenerate_pdf'),
    
    # API
    path('api/warehouse-autocomplete/', views.warehouse_autocomplete, name='warehouse_autocomplete'),
] 