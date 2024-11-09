from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .file_processing import file_processing
import logging
import json
from django.utils.translation import get_language, gettext as _
from django.core.mail import send_mail
from django.contrib import messages
import os
from datetime import datetime

# Configura il logger
logger = logging.getLogger('fbasaving')

def home(request):
    context = {
        'LANGUAGE_CODE': get_language(),
    }
    return render(request, 'fbasaving/fbasaving.html', context)

@csrf_exempt
def upload_file_view(request):
    if request.method == 'POST':
        try:
            file = request.FILES['file']
            results = file_processing(file)
            logger.debug(f"Risultati del processamento del file: {results}")

            # Verifica che 'table_data' sia presente nei risultati
            if 'table_data' not in results:
                logger.error("Chiave 'table_data' mancante nei risultati.")
                return JsonResponse({'error': "Errore nel processamento del file: 'table_data' mancante."}, status=400)

            # Salva 'table_data' nella sessione
            request.session['filtered_data'] = json.dumps(results['table_data'])

            # Restituisci solo i totali al client
            summary = {
                'total_amazon_cost': results['total_amazon_cost'],
                'total_prep_center_cost': results['total_prep_center_cost'],
                'saving': results['saving'],
                'saving_percentage': results['saving_percentage'],
            }

            return JsonResponse(summary)
        except Exception as e:
            logger.error(f"Errore durante l'elaborazione del file: {e}")
            return JsonResponse({'error': str(e)}, status=400)
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)

@csrf_exempt
def data_tables_view(request):
    if request.method == 'POST':
        try:
            draw = int(request.POST.get('draw', 1))
            start = int(request.POST.get('start', 0))
            length = int(request.POST.get('length', 10))

            # Recupera i dati dalla sessione
            data_json = request.session.get('filtered_data', '[]')
            data = json.loads(data_json)

            # Numero totale di record
            records_total = len(data)

            # Implementa la ricerca
            search_value = request.POST.get('search[value]', '').strip()
            if search_value:
                data = [row for row in data if search_value.lower() in str(row).lower()]
                records_filtered = len(data)
            else:
                records_filtered = records_total

            # Ordina i dati
            order_column_index = int(request.POST.get('order[0][column]', 0))
            order_column = request.POST.get(f'columns[{order_column_index}][data]', 'Product')
            order_dir = request.POST.get('order[0][dir]', 'asc')
            data.sort(key=lambda x: x.get(order_column, ''), reverse=(order_dir == 'desc'))

            # Pagina i dati
            data_page = data[start:start+length]

            response = {
                'draw': draw,
                'recordsTotal': records_total,
                'recordsFiltered': records_filtered,
                'data': data_page,
            }

            return JsonResponse(response)
        except Exception as e:
            logger.error(f"Errore durante il server-side processing: {e}")
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)

def contact(request):
    if request.method == 'POST':
        try:
            name = request.POST.get('name')
            phone = request.POST.get('phone')
            notes = request.POST.get('notes', '')
            current_language = request.LANGUAGE_CODE
            
            logger.debug(f"Ricevuta richiesta POST con name={name}, phone={phone}, notes={notes}, language={current_language}")
            
            if not name or not phone:
                logger.warning("Campi obbligatori mancanti nel form")
                messages.error(request, _('Per favore compila tutti i campi obbligatori.'))
                return redirect('fbasaving:home')

            # Prepara il contenuto dell'email
            message = f'''Nome: {name}
Telefono: {phone}
Lingua: {current_language.upper()}\n'''

            if notes:
                message += f'Note: {notes}\n'
            
            # Salva il contenuto in un file
            backup_dir = '/var/www/html/logs/contatti/da_rinviare'
            os.makedirs(backup_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d-%H%M')
            backup_file = os.path.join(backup_dir, f'{timestamp}.txt')
            
            with open(backup_file, 'w', encoding='utf-8') as f:
                f.write(message)
            
            logger.info(f"Backup dati salvato in: {backup_file}")
            
            # Invia l'email
            try:
                send_mail(
                    subject=f'FBA Saving: Nuova richiesta di contatto da {name}',
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[settings.CONTACT_EMAIL],
                    fail_silently=False
                )
                logger.info("Email inviata con successo")
                messages.success(request, _('Grazie! Ti contatteremo al più presto.'))
            except Exception as e:
                logger.error(f"Errore nell'invio dell'email: {str(e)}", exc_info=True)
                messages.error(request, _('Si è verificato un errore nell\'invio dell\'email. Per favore riprova più tardi.'))
            
        except Exception as e:
            logger.error(f"Errore generale: {str(e)}", exc_info=True)
            messages.error(request, _('Si è verificato un errore. Per favore riprova più tardi.'))
        
    return redirect('fbasaving:home')