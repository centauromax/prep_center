from django.urls import path
from . import views
from django.conf.urls.i18n import i18n_patterns
from django.urls import path, include

# Definisci l'URL pattern
urlpatterns = [
    path('', views.home, name='home'),  # Associa l'URL principale alla vista 'home'
    path('upload/', views.upload_file_view, name='upload_file'),  # Aggiungi questa riga
    path('i18n/', include('django.conf.urls.i18n')),
]

def home(request):
    return render(request, 'fbasaving/fbasaving.html')
