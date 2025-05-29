from django.shortcuts import render
from django.contrib.auth.decorators import login_required


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
            'color': 'primary'
        },
        {
            'name': 'FBA Saving',
            'description': 'Confronto costi stoccaggio Amazon vs Prep Center',
            'url': '/fbasaving/',
            'icon': 'fas fa-calculator',
            'color': 'success'
        },
        {
            'name': 'Return Management',
            'description': 'Gestione resi e rimborsi',
            'url': '/return_management/',
            'icon': 'fas fa-undo',
            'color': 'warning'
        },
        {
            'name': 'Picture Check',
            'description': 'Verifica foto prodotti',
            'url': '/picture_check/',
            'icon': 'fas fa-camera',
            'color': 'info'
        },
        {
            'name': 'Pallet Label',
            'description': 'Generazione etichette pallet per Amazon',
            'url': '/pallet_label/',
            'icon': 'fas fa-pallet',
            'color': 'secondary'
        }
    ]
    
    context = {
        'apps': apps,
        'user': request.user
    }
    
    return render(request, 'homepage.html', context) 