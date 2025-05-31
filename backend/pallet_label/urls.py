from django.urls import path
from . import views

app_name = 'pallet_label'

urlpatterns = [
    # Pagina principale unica - creazione e download
    path('', views.pallet_label_list, name='list'),
    
    # Download dell'ultimo PDF
    path('download/', views.download_latest_pdf, name='download'),
    
    # Debug (manteniamo per troubleshooting)
    path('debug/', views.debug_view, name='debug'),
] 