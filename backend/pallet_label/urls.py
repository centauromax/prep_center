from django.urls import path
from . import views

app_name = 'pallet_label'

urlpatterns = [
    # Lista etichette
    path('', views.pallet_label_list, name='list'),
    
    # Creazione etichette
    path('create/', views.pallet_label_create, name='create'),
    
    # Dettagli etichetta
    path('<int:pk>/', views.pallet_label_detail, name='detail'),
    
    # Download PDF
    path('<int:pk>/download/', views.pallet_label_download, name='download'),
    
    # Elimina etichetta
    path('<int:pk>/delete/', views.pallet_label_delete, name='delete'),
    
    # Rigenera PDF
    path('<int:pk>/regenerate-pdf/', views.pallet_label_regenerate_pdf, name='regenerate_pdf'),
    
    # Download multipli
    path('download-all/', views.download_all_pdfs, name='download_all'),
    
    # Debug
    path('debug/', views.debug_view, name='debug'),
] 