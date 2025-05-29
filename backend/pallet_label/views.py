from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.core.paginator import Paginator
from django.db import transaction
from django.views.decorators.http import require_http_methods
from django.urls import reverse
import logging

from .models import PalletLabel
from .forms import PalletLabelForm, QuickPalletForm
from .pdf_generator import generate_pallet_label_pdf

logger = logging.getLogger(__name__)


@login_required
def pallet_label_list(request):
    """
    Vista per elencare tutte le etichette pallet create dall'utente.
    """
    pallet_labels = PalletLabel.objects.filter(created_by=request.user).order_by('-created_at')
    
    # Paginazione
    paginator = Paginator(pallet_labels, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'total_labels': pallet_labels.count()
    }
    
    return render(request, 'pallet_label/list.html', context)


@login_required
def pallet_label_create(request):
    """
    Vista per creare una nuova etichetta pallet.
    """
    if request.method == 'POST':
        form = PalletLabelForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    pallet_label = form.save(commit=False)
                    pallet_label.created_by = request.user
                    pallet_label.save()
                    
                    # Genera il PDF
                    pdf_file = generate_pallet_label_pdf(pallet_label)
                    pallet_label.pdf_file.save(pdf_file.name, pdf_file)
                    pallet_label.pdf_generated = True
                    pallet_label.save()
                    
                    messages.success(request, f'Etichetta pallet {pallet_label.pallet_id} creata con successo!')
                    return redirect('pallet_label:detail', pk=pallet_label.pk)
                    
            except Exception as e:
                logger.error(f"Errore nella creazione dell'etichetta pallet: {str(e)}")
                messages.error(request, 'Errore nella creazione dell\'etichetta. Riprova.')
    else:
        form = PalletLabelForm()
    
    context = {
        'form': form,
        'title': 'Crea Nuova Etichetta Pallet'
    }
    
    return render(request, 'pallet_label/create.html', context)


@login_required
def pallet_label_quick_create(request):
    """
    Vista per la creazione rapida di etichette con dati precompilati.
    """
    if request.method == 'POST':
        form = QuickPalletForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Dati dal form
                    pallet_id_base = form.cleaned_data['pallet_id']
                    amazon_warehouse_code = form.cleaned_data['amazon_warehouse_code']
                    shipment_id = form.cleaned_data['shipment_id']
                    total_boxes = form.cleaned_data['total_boxes']
                    pallet_weight = form.cleaned_data['pallet_weight']
                    pallet_count = form.cleaned_data['pallet_count']
                    generate_all = form.cleaned_data['generate_all']
                    
                    # Dati precompilati (puoi personalizzare questi valori)
                    default_data = {
                        'sender_name': 'Prep Center Italy',
                        'sender_address_line1': 'Via Example 123',
                        'sender_city': 'Milano',
                        'sender_postal_code': '20100',
                        'sender_country': 'Italia',
                        'amazon_warehouse_name': f'Amazon Warehouse {amazon_warehouse_code}',
                        'amazon_address_line1': 'Indirizzo Amazon',
                        'amazon_city': 'Città Amazon',
                        'amazon_postal_code': '00000',
                        'amazon_country': 'Italia',
                        'pallet_dimensions_length': 120,
                        'pallet_dimensions_width': 80,
                        'pallet_dimensions_height': 180,
                    }
                    
                    created_labels = []
                    
                    if generate_all and pallet_count > 1:
                        # Genera etichette per tutti i pallet
                        for i in range(1, pallet_count + 1):
                            pallet_label = PalletLabel(
                                created_by=request.user,
                                pallet_id=f"{pallet_id_base}-{i:02d}",
                                amazon_warehouse_code=amazon_warehouse_code,
                                shipment_id=shipment_id,
                                total_boxes=total_boxes,
                                pallet_weight=pallet_weight,
                                pallet_count=pallet_count,
                                pallet_number=i,
                                **default_data
                            )
                            pallet_label.save()
                            
                            # Genera PDF
                            pdf_file = generate_pallet_label_pdf(pallet_label)
                            pallet_label.pdf_file.save(pdf_file.name, pdf_file)
                            pallet_label.pdf_generated = True
                            pallet_label.save()
                            
                            created_labels.append(pallet_label)
                    else:
                        # Genera solo un'etichetta
                        pallet_label = PalletLabel(
                            created_by=request.user,
                            pallet_id=pallet_id_base,
                            amazon_warehouse_code=amazon_warehouse_code,
                            shipment_id=shipment_id,
                            total_boxes=total_boxes,
                            pallet_weight=pallet_weight,
                            pallet_count=pallet_count,
                            pallet_number=1,
                            **default_data
                        )
                        pallet_label.save()
                        
                        # Genera PDF
                        pdf_file = generate_pallet_label_pdf(pallet_label)
                        pallet_label.pdf_file.save(pdf_file.name, pdf_file)
                        pallet_label.pdf_generated = True
                        pallet_label.save()
                        
                        created_labels.append(pallet_label)
                    
                    if len(created_labels) == 1:
                        messages.success(request, f'Etichetta pallet {created_labels[0].pallet_id} creata con successo!')
                        return redirect('pallet_label:detail', pk=created_labels[0].pk)
                    else:
                        messages.success(request, f'{len(created_labels)} etichette pallet create con successo!')
                        return redirect('pallet_label:list')
                        
            except Exception as e:
                logger.error(f"Errore nella creazione rapida delle etichette: {str(e)}")
                messages.error(request, 'Errore nella creazione delle etichette. Riprova.')
    else:
        form = QuickPalletForm()
    
    context = {
        'form': form,
        'title': 'Creazione Rapida Etichette Pallet'
    }
    
    return render(request, 'pallet_label/quick_create.html', context)


@login_required
def pallet_label_detail(request, pk):
    """
    Vista per visualizzare i dettagli di un'etichetta pallet.
    """
    pallet_label = get_object_or_404(PalletLabel, pk=pk, created_by=request.user)
    
    context = {
        'pallet_label': pallet_label
    }
    
    return render(request, 'pallet_label/detail.html', context)


@login_required
def pallet_label_edit(request, pk):
    """
    Vista per modificare un'etichetta pallet esistente.
    """
    pallet_label = get_object_or_404(PalletLabel, pk=pk, created_by=request.user)
    
    if request.method == 'POST':
        form = PalletLabelForm(request.POST, instance=pallet_label)
        if form.is_valid():
            try:
                with transaction.atomic():
                    pallet_label = form.save()
                    
                    # Rigenera il PDF
                    pdf_file = generate_pallet_label_pdf(pallet_label)
                    pallet_label.pdf_file.save(pdf_file.name, pdf_file)
                    pallet_label.pdf_generated = True
                    pallet_label.save()
                    
                    messages.success(request, f'Etichetta pallet {pallet_label.pallet_id} aggiornata con successo!')
                    return redirect('pallet_label:detail', pk=pallet_label.pk)
                    
            except Exception as e:
                logger.error(f"Errore nell'aggiornamento dell'etichetta pallet: {str(e)}")
                messages.error(request, 'Errore nell\'aggiornamento dell\'etichetta. Riprova.')
    else:
        form = PalletLabelForm(instance=pallet_label)
    
    context = {
        'form': form,
        'pallet_label': pallet_label,
        'title': f'Modifica Etichetta {pallet_label.pallet_id}'
    }
    
    return render(request, 'pallet_label/edit.html', context)


@login_required
def pallet_label_download(request, pk):
    """
    Vista per scaricare il PDF di un'etichetta pallet.
    """
    pallet_label = get_object_or_404(PalletLabel, pk=pk, created_by=request.user)
    
    if not pallet_label.pdf_file:
        # Genera il PDF se non esiste
        try:
            pdf_file = generate_pallet_label_pdf(pallet_label)
            pallet_label.pdf_file.save(pdf_file.name, pdf_file)
            pallet_label.pdf_generated = True
            pallet_label.save()
        except Exception as e:
            logger.error(f"Errore nella generazione del PDF: {str(e)}")
            messages.error(request, 'Errore nella generazione del PDF.')
            return redirect('pallet_label:detail', pk=pk)
    
    # Restituisci il file PDF
    response = HttpResponse(pallet_label.pdf_file.read(), content_type='application/pdf')
    filename = f"pallet_label_{pallet_label.pallet_id}_{pallet_label.pallet_number}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response


@login_required
@require_http_methods(["POST"])
def pallet_label_delete(request, pk):
    """
    Vista per eliminare un'etichetta pallet.
    """
    pallet_label = get_object_or_404(PalletLabel, pk=pk, created_by=request.user)
    
    try:
        pallet_id = pallet_label.pallet_id
        pallet_label.delete()
        messages.success(request, f'Etichetta pallet {pallet_id} eliminata con successo!')
    except Exception as e:
        logger.error(f"Errore nell'eliminazione dell'etichetta pallet: {str(e)}")
        messages.error(request, 'Errore nell\'eliminazione dell\'etichetta.')
    
    return redirect('pallet_label:list')


@login_required
def pallet_label_regenerate_pdf(request, pk):
    """
    Vista per rigenerare il PDF di un'etichetta pallet.
    """
    pallet_label = get_object_or_404(PalletLabel, pk=pk, created_by=request.user)
    
    try:
        # Rigenera il PDF
        pdf_file = generate_pallet_label_pdf(pallet_label)
        pallet_label.pdf_file.save(pdf_file.name, pdf_file)
        pallet_label.pdf_generated = True
        pallet_label.save()
        
        messages.success(request, f'PDF dell\'etichetta {pallet_label.pallet_id} rigenerato con successo!')
    except Exception as e:
        logger.error(f"Errore nella rigenerazione del PDF: {str(e)}")
        messages.error(request, 'Errore nella rigenerazione del PDF.')
    
    return redirect('pallet_label:detail', pk=pk)


@login_required
def warehouse_autocomplete(request):
    """
    API per l'autocompletamento dei warehouse Amazon.
    """
    query = request.GET.get('q', '').upper()
    
    # Lista di warehouse Amazon comuni (puoi espandere questa lista)
    warehouses = {
        'MXP5': {'name': 'Amazon MXP5 - Castel San Giovanni', 'city': 'Castel San Giovanni', 'country': 'Italia'},
        'LIN1': {'name': 'Amazon LIN1 - Linate', 'city': 'Linate', 'country': 'Italia'},
        'FCO1': {'name': 'Amazon FCO1 - Passo Corese', 'city': 'Passo Corese', 'country': 'Italia'},
        'VCE1': {'name': 'Amazon VCE1 - Venezia', 'city': 'Venezia', 'country': 'Italia'},
        'TXL2': {'name': 'Amazon TXL2 - Berlin', 'city': 'Berlin', 'country': 'Germania'},
        'DUS2': {'name': 'Amazon DUS2 - Düsseldorf', 'city': 'Düsseldorf', 'country': 'Germania'},
        'MUC1': {'name': 'Amazon MUC1 - München', 'city': 'München', 'country': 'Germania'},
        'CDG6': {'name': 'Amazon CDG6 - Paris', 'city': 'Paris', 'country': 'Francia'},
        'LYS1': {'name': 'Amazon LYS1 - Lyon', 'city': 'Lyon', 'country': 'Francia'},
        'MAD4': {'name': 'Amazon MAD4 - Madrid', 'city': 'Madrid', 'country': 'Spagna'},
        'BCN1': {'name': 'Amazon BCN1 - Barcelona', 'city': 'Barcelona', 'country': 'Spagna'},
    }
    
    results = []
    for code, info in warehouses.items():
        if query in code or query in info['name'].upper():
            results.append({
                'code': code,
                'name': info['name'],
                'city': info['city'],
                'country': info['country']
            })
    
    return JsonResponse({'results': results})
