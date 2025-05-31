from django.urls import path
from . import views

app_name = 'pallet_label'

urlpatterns = [
    # Lista spedizioni (semplificata)
    path('', views.pallet_label_list, name='list'),
    
    # Creazione etichette
    path('create/', views.pallet_label_create, name='create'),
    
    # Nuove rotte semplificate per spedizioni
    path('spedizione/<str:numero_spedizione>/', views.shipment_detail, name='shipment_detail'),
    path('spedizione/<str:numero_spedizione>/download/', views.shipment_download, name='shipment_download'),
    path('spedizione/<str:numero_spedizione>/delete/', views.shipment_delete, name='shipment_delete'),
    
    # Vecchie rotte per compatibilità (deprecate)
    path('<int:pk>/', views.pallet_label_detail, name='detail'),
    path('<int:pk>/download/', views.pallet_label_download, name='download'),
    path('<int:pk>/delete/', views.pallet_label_delete, name='delete'),
    path('<int:pk>/regenerate-pdf/', views.pallet_label_regenerate_pdf, name='regenerate_pdf'),
    
    # Download multipli (deprecato)
    path('download-all/', views.download_all_pdfs, name='download_all'),
    
    # Debug
    path('debug/', views.debug_view, name='debug'),
] 