from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.core.paginator import Paginator
from django.db import transaction
from django.views.decorators.http import require_http_methods
from django.urls import reverse
import logging
import json

from .models import PalletLabel
from .forms import PalletLabelForm

logger = logging.getLogger(__name__)

# Importazione condizionale per evitare errori se ReportLab non è disponibile
try:
    from .pdf_generator import generate_pallet_label_pdf, generate_shipment_labels_pdf
    PDF_AVAILABLE = True
except ImportError as e:
    logger.error(f"Errore nell'importazione del PDF generator: {str(e)}")
    PDF_AVAILABLE = False
    def generate_pallet_label_pdf(pallet_label):
        raise ImportError("ReportLab non disponibile")


def pallet_label_list(request):
    """
    Vista per elencare tutte le etichette pallet create.
    """
    try:
        # Se l'utente è autenticato, mostra solo le sue etichette
        # Altrimenti mostra tutte le etichette (per demo)
        if request.user.is_authenticated:
            pallet_labels = PalletLabel.objects.filter(created_by=request.user).order_by('-created_at')
        else:
            pallet_labels = PalletLabel.objects.all().order_by('-created_at')
        
        # Paginazione
        paginator = Paginator(pallet_labels, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        context = {
            'page_obj': page_obj,
            'total_labels': pallet_labels.count(),
            'pdf_available': PDF_AVAILABLE
        }
        
        return render(request, 'pallet_label/list.html', context)
        
    except Exception as e:
        logger.error(f"Errore nella vista pallet_label_list: {str(e)}")
        messages.error(request, f'Errore nel caricamento delle etichette: {str(e)}')
        return render(request, 'pallet_label/list.html', {
            'page_obj': None,
            'total_labels': 0,
            'pdf_available': PDF_AVAILABLE,
            'error': str(e)
        })


def pallet_label_create(request):
    """
    Vista per creare nuove etichette pallet.
    """
    if request.method == 'POST':
        form = PalletLabelForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Estrai i dati dal form
                    nome_venditore = form.cleaned_data['nome_venditore']
                    nome_spedizione = form.cleaned_data['nome_spedizione']
                    numero_spedizione = form.cleaned_data['numero_spedizione']
                    indirizzo_spedizione = form.cleaned_data['indirizzo_spedizione']
                    numero_pallet = form.cleaned_data['numero_pallet']
                    cartoni_per_pallet = form.get_cartoni_data()
                    
                    # Determina l'utente
                    if request.user.is_authenticated:
                        user = request.user
                    else:
                        from django.contrib.auth.models import User
                        user, created = User.objects.get_or_create(
                            username='demo_user',
                            defaults={'email': 'demo@example.com', 'first_name': 'Demo', 'last_name': 'User'}
                        )
                    
                    # Crea le etichette per ogni pallet
                    created_labels = []
                    for i, num_cartoni in enumerate(cartoni_per_pallet, 1):
                        pallet_label = PalletLabel(
                            created_by=user,
                            nome_venditore=nome_venditore,
                            nome_spedizione=nome_spedizione,
                            numero_spedizione=numero_spedizione,
                            indirizzo_spedizione=indirizzo_spedizione,
                            pallet_numero=i,
                            pallet_totale=numero_pallet,
                            numero_cartoni=int(num_cartoni)
                        )
                        pallet_label.save()
                        created_labels.append(pallet_label)
                    
                    # Genera un unico PDF per tutta la spedizione
                    if PDF_AVAILABLE and created_labels:
                        try:
                            queryset = PalletLabel.objects.filter(
                                numero_spedizione=numero_spedizione,
                                created_by=user
                            ).order_by('pallet_numero')
                            
                            pdf_file = generate_shipment_labels_pdf(queryset)
                            
                            # Salva il PDF solo per la prima etichetta (per evitare duplicazioni)
                            filename = f"etichette_spedizione_{numero_spedizione}.pdf"
                            first_label = created_labels[0]
                            first_label.pdf_file.save(filename, pdf_file)
                            first_label.pdf_generated = True
                            first_label.save()
                                
                        except Exception as pdf_error:
                            logger.error(f"Errore nella generazione PDF: {str(pdf_error)}")
                            # Non bloccare la creazione delle etichette se il PDF fallisce
                    
                    # Messaggio di successo e redirect
                    if len(created_labels) == 1:
                        messages.success(request, f'Etichetta pallet per {nome_venditore} creata con successo!')
                        return redirect('pallet_label:detail', pk=created_labels[0].pk)
                    else:
                        messages.success(request, f'{len(created_labels)} etichette pallet per {nome_venditore} create con successo!')
                        return redirect('pallet_label:list')
                        
            except Exception as e:
                logger.error(f"Errore nella creazione delle etichette: {str(e)}")
                messages.error(request, 'Errore nella creazione delle etichette. Riprova.')
    else:
        form = PalletLabelForm()
    
    context = {
        'form': form,
        'title': 'Crea Nuove Etichette Pallet'
    }
    
    return render(request, 'pallet_label/create.html', context)


def pallet_label_detail(request, pk):
    """
    Vista per visualizzare i dettagli di un'etichetta pallet.
    """
    # Se l'utente è autenticato, filtra per utente, altrimenti mostra tutte
    if request.user.is_authenticated:
        pallet_label = get_object_or_404(PalletLabel, pk=pk, created_by=request.user)
    else:
        pallet_label = get_object_or_404(PalletLabel, pk=pk)
    
    # Trova altre etichette della stessa spedizione
    related_labels = PalletLabel.objects.filter(
        numero_spedizione=pallet_label.numero_spedizione
    ).exclude(pk=pk).order_by('pallet_numero')
    
    context = {
        'pallet_label': pallet_label,
        'related_labels': related_labels
    }
    
    return render(request, 'pallet_label/detail.html', context)


def pallet_label_download(request, pk):
    """
    Vista per scaricare il PDF di una spedizione (tutte le etichette).
    """
    # Se l'utente è autenticato, filtra per utente, altrimenti mostra tutte
    if request.user.is_authenticated:
        pallet_label = get_object_or_404(PalletLabel, pk=pk, created_by=request.user)
    else:
        pallet_label = get_object_or_404(PalletLabel, pk=pk)
    
    # Controlla se il PDF esiste, altrimenti lo genera
    if not pallet_label.pdf_file and PDF_AVAILABLE:
        try:
            from .pdf_generator import generate_shipment_labels_pdf
            
            # Trova tutte le etichette della stessa spedizione
            if request.user.is_authenticated:
                queryset = PalletLabel.objects.filter(
                    numero_spedizione=pallet_label.numero_spedizione,
                    created_by=request.user
                ).order_by('pallet_numero')
            else:
                queryset = PalletLabel.objects.filter(
                    numero_spedizione=pallet_label.numero_spedizione
                ).order_by('pallet_numero')
            
            pdf_file = generate_shipment_labels_pdf(queryset)
            filename = f"etichette_spedizione_{pallet_label.numero_spedizione}.pdf"
            
            # Salva il PDF per tutte le etichette della spedizione
            for label in queryset:
                label.pdf_file.save(filename, pdf_file)
                label.pdf_generated = True
                label.save()
                pdf_file.seek(0)
                
        except Exception as e:
            logger.error(f"Errore nella generazione del PDF: {str(e)}")
            messages.error(request, 'Errore nella generazione del PDF.')
            return redirect('pallet_label:detail', pk=pk)
    
    if not pallet_label.pdf_file:
        messages.error(request, 'PDF non disponibile.')
        return redirect('pallet_label:detail', pk=pk)
    
    # Restituisci il file PDF
    filename = f"etichette_spedizione_{pallet_label.numero_spedizione}.pdf"
    response = HttpResponse(pallet_label.pdf_file.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response


@require_http_methods(["POST"])
def pallet_label_delete(request, pk):
    """
    Vista per eliminare un'etichetta pallet.
    """
    # Se l'utente è autenticato, filtra per utente, altrimenti mostra tutte
    if request.user.is_authenticated:
        pallet_label = get_object_or_404(PalletLabel, pk=pk, created_by=request.user)
    else:
        pallet_label = get_object_or_404(PalletLabel, pk=pk)
    
    try:
        numero_spedizione = pallet_label.numero_spedizione
        pallet_label.delete()
        messages.success(request, f'Etichetta eliminata con successo!')
    except Exception as e:
        logger.error(f"Errore nell'eliminazione dell'etichetta: {str(e)}")
        messages.error(request, 'Errore nell\'eliminazione dell\'etichetta.')
    
    return redirect('pallet_label:list')


def pallet_label_regenerate_pdf(request, pk):
    """
    Vista per rigenerare il PDF di una spedizione (tutte le etichette).
    """
    # Se l'utente è autenticato, filtra per utente, altrimenti mostra tutte
    if request.user.is_authenticated:
        pallet_label = get_object_or_404(PalletLabel, pk=pk, created_by=request.user)
    else:
        pallet_label = get_object_or_404(PalletLabel, pk=pk)
    
    if not PDF_AVAILABLE:
        messages.error(request, 'Generazione PDF non disponibile.')
        return redirect('pallet_label:detail', pk=pk)
    
    try:
        from .pdf_generator import generate_shipment_labels_pdf
        
        # Trova tutte le etichette della stessa spedizione
        if request.user.is_authenticated:
            queryset = PalletLabel.objects.filter(
                numero_spedizione=pallet_label.numero_spedizione,
                created_by=request.user
            ).order_by('pallet_numero')
        else:
            queryset = PalletLabel.objects.filter(
                numero_spedizione=pallet_label.numero_spedizione
            ).order_by('pallet_numero')
        
        # Rigenera il PDF per tutta la spedizione
        pdf_file = generate_shipment_labels_pdf(queryset)
        filename = f"etichette_spedizione_{pallet_label.numero_spedizione}.pdf"
        
        # Salva il PDF per tutte le etichette della spedizione
        for label in queryset:
            label.pdf_file.save(filename, pdf_file)
            label.pdf_generated = True
            label.save()
            pdf_file.seek(0)
        
        messages.success(request, f'PDF della spedizione {pallet_label.numero_spedizione} rigenerato con successo!')
    except Exception as e:
        logger.error(f"Errore nella rigenerazione del PDF: {str(e)}")
        messages.error(request, 'Errore nella rigenerazione del PDF.')
    
    return redirect('pallet_label:detail', pk=pk)


def download_all_pdfs(request):
    """
    Vista per scaricare tutti i PDF di una spedizione.
    """
    numero_spedizione = request.GET.get('numero_spedizione')
    if not numero_spedizione:
        messages.error(request, 'Numero spedizione non specificato.')
        return redirect('pallet_label:list')
    
    # Filtra le etichette per utente se autenticato
    if request.user.is_authenticated:
        labels = PalletLabel.objects.filter(
            numero_spedizione=numero_spedizione,
            created_by=request.user
        ).order_by('pallet_numero')
    else:
        labels = PalletLabel.objects.filter(
            numero_spedizione=numero_spedizione
        ).order_by('pallet_numero')
    
    if not labels.exists():
        messages.error(request, 'Nessuna etichetta trovata per questa spedizione.')
        return redirect('pallet_label:list')
    
    # Per ora reindirizza alla lista, in futuro si può implementare un ZIP
    messages.info(request, f'Trovate {labels.count()} etichette per la spedizione {numero_spedizione}')
    return redirect('pallet_label:list')


def debug_view(request):
    """
    Vista di debug per testare se l'app funziona.
    """
    import sys
    import django
    
    debug_info = {
        'django_version': django.get_version(),
        'python_version': sys.version,
        'pdf_available': PDF_AVAILABLE,
        'user_authenticated': request.user.is_authenticated,
        'user': str(request.user) if request.user.is_authenticated else 'Anonymous'
    }
    
    try:
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM django_migrations WHERE app = 'pallet_label'")
            migrations_count = cursor.fetchone()[0]
        debug_info['pallet_label_migrations'] = migrations_count
    except Exception as e:
        debug_info['migration_error'] = str(e)
    
    return JsonResponse(debug_info)


def shipment_detail(request, numero_spedizione):
    """
    Vista semplificata per visualizzare una spedizione completa.
    """
    # Filtra per utente se autenticato
    if request.user.is_authenticated:
        labels = PalletLabel.objects.filter(
            numero_spedizione=numero_spedizione,
            created_by=request.user
        ).order_by('pallet_numero')
    else:
        labels = PalletLabel.objects.filter(
            numero_spedizione=numero_spedizione
        ).order_by('pallet_numero')
    
    if not labels.exists():
        messages.error(request, 'Spedizione non trovata.')
        return redirect('pallet_label:list')
    
    first_label = labels.first()
    
    context = {
        'labels': labels,
        'first_label': first_label,
        'numero_spedizione': numero_spedizione,
        'total_pallet': labels.count(),
        'total_cartoni': sum(label.numero_cartoni for label in labels),
        'pdf_available': first_label.pdf_generated and first_label.pdf_file
    }
    
    return render(request, 'pallet_label/shipment_detail.html', context)


def shipment_download(request, numero_spedizione):
    """
    Vista semplificata per scaricare il PDF di una spedizione.
    """
    # Filtra per utente se autenticato
    if request.user.is_authenticated:
        labels = PalletLabel.objects.filter(
            numero_spedizione=numero_spedizione,
            created_by=request.user
        ).order_by('pallet_numero')
    else:
        labels = PalletLabel.objects.filter(
            numero_spedizione=numero_spedizione
        ).order_by('pallet_numero')
    
    if not labels.exists():
        messages.error(request, 'Spedizione non trovata.')
        return redirect('pallet_label:list')
    
    first_label = labels.first()
    
    # Genera o rigenera il PDF se necessario
    if not first_label.pdf_file and PDF_AVAILABLE:
        try:
            from .pdf_generator import generate_shipment_labels_pdf
            pdf_file = generate_shipment_labels_pdf(labels)
            filename = f"etichette_spedizione_{numero_spedizione}.pdf"
            first_label.pdf_file.save(filename, pdf_file)
            first_label.pdf_generated = True
            first_label.save()
        except Exception as e:
            logger.error(f"Errore nella generazione del PDF: {str(e)}")
            messages.error(request, 'Errore nella generazione del PDF.')
            return redirect('pallet_label:shipment_detail', numero_spedizione=numero_spedizione)
    
    if not first_label.pdf_file:
        messages.error(request, 'PDF non disponibile.')
        return redirect('pallet_label:shipment_detail', numero_spedizione=numero_spedizione)
    
    # Restituisci il file PDF
    filename = f"etichette_spedizione_{numero_spedizione}.pdf"
    response = HttpResponse(first_label.pdf_file.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response


@require_http_methods(["POST"])
def shipment_delete(request, numero_spedizione):
    """
    Vista per eliminare un'intera spedizione.
    """
    # Filtra per utente se autenticato
    if request.user.is_authenticated:
        labels = PalletLabel.objects.filter(
            numero_spedizione=numero_spedizione,
            created_by=request.user
        )
    else:
        labels = PalletLabel.objects.filter(
            numero_spedizione=numero_spedizione
        )
    
    if not labels.exists():
        messages.error(request, 'Spedizione non trovata.')
        return redirect('pallet_label:list')
    
    try:
        count = labels.count()
        labels.delete()
        messages.success(request, f'Spedizione {numero_spedizione} con {count} pallet eliminata con successo!')
    except Exception as e:
        logger.error(f"Errore nell'eliminazione della spedizione: {str(e)}")
        messages.error(request, 'Errore nell\'eliminazione della spedizione.')
    
    return redirect('pallet_label:list')
