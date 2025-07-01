from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponsePermanentRedirect, HttpResponse


def test_view(request):
    """
    Vista di test per verificare se Django risponde.
    """
    host = request.get_host()
    path = request.get_full_path()
    
    return HttpResponse(f"""
        <h1>Test Django Response</h1>
        <p><strong>Host:</strong> {host}</p>
        <p><strong>Path:</strong> {path}</p>
        <p><strong>User:</strong> {request.user}</p>
        <p><strong>Time:</strong> {request.META.get('HTTP_DATE', 'N/A')}</p>
        <hr>
        <p>Se vedi questo messaggio, Django sta funzionando!</p>
        <p><a href="https://backend.fbaprepcenteritaly.com/">Vai alla homepage unificata</a></p>
    """, content_type='text/html')


@login_required
def homepage(request):
    """
    Homepage unificata con tutte le app disponibili.
    """
    apps = [
        {
            'name': 'Prep Management',
            'description': 'Gestione merchants e webhook Prep Business',
            'url': '/prep_management/',
            'icon': 'fas fa-shipping-fast',
            'color': 'primary',
            'type': 'django'
        },
        {
            'name': 'FBA Saving',
            'description': 'Confronto costi stoccaggio Amazon vs Prep Center',
            'url': '/fbasaving/',
            'icon': 'fas fa-calculator',
            'color': 'success',
            'type': 'django'
        },
        {
            'name': 'Return Management',
            'description': 'Gestione resi e rimborsi',
            'url': '/return_management/',
            'icon': 'fas fa-undo',
            'color': 'warning',
            'type': 'django'
        },
        {
            'name': 'Picture Check',
            'description': 'Verifica foto prodotti',
            'url': 'https://apppc.fbaprepcenteritaly.com/picture_check/',
            'icon': 'fas fa-camera',
            'color': 'info',
            'type': 'react'
        },
        {
            'name': 'Pallet Label',
            'description': 'Generazione etichette pallet per Amazon',
            'url': '/pallet_label/',
            'icon': 'fas fa-pallet',
            'color': 'secondary',
            'type': 'django'
        },
        {
            'name': 'Rifornimento',
            'description': 'Gestione richieste di rifornimento e stock prodotti',
            'url': '/rifornimento/',
            'icon': 'fas fa-warehouse',
            'color': 'danger',
            'type': 'django'
        }
    ]
    
    context = {
        'apps': apps,
        'user': request.user
    }
    
    return render(request, 'homepage.html', context) 