from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.http import HttpResponse
from django.shortcuts import render
from .models import ProductReturn

@login_required
def home(request):
    return render(request, 'return_management/home.html')

def product_return_list(request):
    # Otteniamo tutti i record della tabella ProductReturn
    product_returns = ProductReturn.objects.all()
    return render(request, 'return_management/product_return_list.html', {'product_returns': product_returns})

def product_return_edit(request):
    # Otteniamo tutti i record della tabella ProductReturn
    product_returns = ProductReturn.objects.all()

    if request.method == 'POST':
        # Aggiungi la logica per aggiornare i record qui
        pass

    return render(request, 'return_management/product_return_edit.html', {'product_returns': product_returns})
