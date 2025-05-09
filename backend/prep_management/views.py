from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .services import PrepBusinessAPI
from .utils.merchants import get_merchants
from .models import ShipmentStatusUpdate, OutgoingMessage
from .serializers import OutgoingMessageSerializer
import logging
import requests
import traceback
import json
import os
import hmac
import hashlib
import base64
import time
import socket
from libs.prepbusiness.webhook_manager import list_webhooks, create_webhook, delete_webhook, test_webhook, update_webhook
from libs.prepbusiness.webhook_processor import WebhookProcessor
from libs.prepbusiness.webhook_receiver import WebhookReceiver
from .event_handlers import WebhookEventProcessor
from django.utils import timezone
from datetime import timedelta
from libs.prepbusiness.client import PrepBusinessClient
from libs.config import PREP_BUSINESS_API_KEY, PREP_BUSINESS_API_URL
from enum import Enum

from libs.config import (
    PREP_BUSINESS_API_URL,
    PREP_BUSINESS_API_KEY,
    PREP_BUSINESS_API_TIMEOUT,
    PREP_BUSINESS_MAX_RETRIES,
    PREP_BUSINESS_RETRY_BACKOFF
)

logger = logging.getLogger('prep_management')

def index(request):
    return render(request, 'prep_management/index.html')

def open_shipments(request):
    api = PrepBusinessAPI(settings.PREP_BUSINESS_API_KEY)
    data = api.get_open_inbound_shipments()
    return JsonResponse(data, safe=False)

def merchants_list(request):
    """
    View per visualizzare la lista dei merchants da Prep Business.
    """
    # Ottieni tutti i merchants (anche non attivi se specificato)
    show_inactive = request.GET.get('show_inactive', 'false').lower() == 'true'
    merchants = get_merchants(active_only=not show_inactive)
    
    # Prepara il contesto per il template
    context = {
        'merchants': merchants,
        'total_merchants': len(merchants),
        'show_inactive': show_inactive,
        'title': 'Merchants Prep Business'
    }
    
    return render(request, 'prep_management/merchants.html', context)

def api_config_debug(request):
    """
    View di debug per visualizzare e testare le configurazioni API.
    Solo per sviluppo e debug.
    """
    # Raccogli info sulle variabili d'ambiente
    env_vars = {
        'PREP_BUSINESS_API_URL': os.environ.get('PREP_BUSINESS_API_URL', 'non impostata'),
        'PREP_BUSINESS_API_KEY': os.environ.get('PREP_BUSINESS_API_KEY', 'non impostata')[:4] + '...' if os.environ.get('PREP_BUSINESS_API_KEY') and len(os.environ.get('PREP_BUSINESS_API_KEY')) > 4 else 'non impostata',
        'PREP_BUSINESS_API_TIMEOUT': os.environ.get('PREP_BUSINESS_API_TIMEOUT', 'non impostata'),
        'PREP_BUSINESS_MAX_RETRIES': os.environ.get('PREP_BUSINESS_MAX_RETRIES', 'non impostata'),
        'PREP_BUSINESS_RETRY_BACKOFF': os.environ.get('PREP_BUSINESS_RETRY_BACKOFF', 'non impostata'),
    }
    
    # Raccogli info sulle configurazioni correnti
    current_config = {
        'API_URL': PREP_BUSINESS_API_URL,
        'API_KEY': PREP_BUSINESS_API_KEY[:4] + '...' if PREP_BUSINESS_API_KEY and len(PREP_BUSINESS_API_KEY) > 4 else 'non impostata',
        'API_TIMEOUT': PREP_BUSINESS_API_TIMEOUT,
        'MAX_RETRIES': PREP_BUSINESS_MAX_RETRIES,
        'RETRY_BACKOFF': PREP_BUSINESS_RETRY_BACKOFF,
    }
    
    # Test di connessione all'API
    test_result = None
    
    if request.GET.get('test_api') == 'true':
        try:
            logger.info(f"Test connessione API a {PREP_BUSINESS_API_URL}")
            headers = {
                'Authorization': f'Bearer {PREP_BUSINESS_API_KEY}',
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            }
            
            # Test di connessione all'endpoint merchants
            response = requests.get(
                f"{PREP_BUSINESS_API_URL}/merchants",
                headers=headers,
                timeout=PREP_BUSINESS_API_TIMEOUT
            )
            
            test_result = {
                'success': response.status_code < 400,
                'status_code': response.status_code,
                'status_text': response.reason,
                'headers': dict(response.headers),
                'content': response.text[:500] + ('...' if len(response.text) > 500 else ''),
            }
            
            try:
                test_result['json'] = response.json()
            except:
                test_result['json'] = None
                
            logger.info(f"Test API completato: status={response.status_code}")
            
        except Exception as e:
            logger.error(f"Errore nel test API: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            test_result = {
                'success': False,
                'error': str(e),
                'traceback': traceback.format_exc(),
            }
    
    context = {
        'env_vars': env_vars,
        'current_config': current_config,
        'test_result': test_result,
        'title': 'Debug configurazione API',
    }
    
    return render(request, 'prep_management/api_debug.html', context)


@csrf_exempt
def shipment_status_webhook(request):
    """
    Webhook per ricevere notifiche di cambio stato delle spedizioni.
    
    Questo endpoint riceve notifiche POST quando lo stato di una spedizione cambia.
    Salva i dati ricevuti nel database per essere visualizzati e processati.
    """
    # Ottieni la chiave segreta per verificare i webhook
    webhook_secret = os.environ.get('PREP_BUSINESS_WEBHOOK_SECRET')
    
    # Crea il gestore webhook e il processore degli eventi
    receiver = WebhookReceiver(webhook_secret=webhook_secret)
    processor = WebhookEventProcessor()
    
    # Definisci la funzione di callback per salvare e processare subito i dati
    def save_webhook_data(webhook_data):
        # Recupera il nome del merchant usando il team_id
        merchant_id = webhook_data.get('merchant_id')
        merchant_name = None
        if merchant_id:
            try:
                merchants = get_merchants()
                merchant = next((m for m in merchants if str(m['id']) == str(merchant_id)), None)
                if merchant:
                    merchant_name = merchant['name']
            except Exception as e:
                logger.error(f"Errore nel recupero del nome del merchant: {str(e)}")

        # Crea il record di aggiornamento
        shipment_update = ShipmentStatusUpdate(
            shipment_id=webhook_data.get('shipment_id'),
            event_type=webhook_data.get('event_type', 'other'),
            entity_type=webhook_data.get('entity_type', ''),
            previous_status=webhook_data.get('previous_status'),
            new_status=webhook_data.get('new_status', 'other'),
            merchant_id=merchant_id,
            merchant_name=merchant_name,
            tracking_number=webhook_data.get('tracking_number'),
            carrier=webhook_data.get('carrier'),
            notes=webhook_data.get('notes'),
            payload=webhook_data.get('payload', {})
        )
        shipment_update.save()
        # Elabora subito l'evento appena salvato
        processor.process_event(shipment_update.id)
        return shipment_update
    
    # Processa il webhook
    response, webhook_data = receiver.process_webhook(request, save_callback=save_webhook_data)
    return response


def test_webhook(request):
    """
    Endpoint per verificare che il webhook sia raggiungibile.
    Utile per debug e verifica della connettività.
    """
    # Info di base
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    
    # Info su Railway
    is_railway = bool(os.environ.get('RAILWAY_STATIC_URL') or os.environ.get('RAILWAY_PUBLIC_DOMAIN'))
    railway_url = None
    if is_railway:
        domain = os.environ.get('RAILWAY_STATIC_URL') or os.environ.get('RAILWAY_PUBLIC_DOMAIN')
        if domain:
            railway_url = f"https://{domain}" if not domain.startswith('http') else domain
    
    # URL completo del webhook
    webhook_url = f"{request.scheme}://{request.get_host()}/prep_management/webhook/"
    
    return JsonResponse({
        'status': 'ok',
        'message': 'Webhook endpoint is reachable',
        'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
        'hostname': hostname,
        'local_ip': local_ip,
        'is_railway': is_railway,
        'railway_url': railway_url,
        'webhook_url': webhook_url,
        'headers': dict(request.headers),
    })


def shipment_status_updates(request):
    """
    View per visualizzare gli aggiornamenti di stato delle spedizioni.
    """
    # Filtri
    status_filter = request.GET.get('status')
    processed_filter = request.GET.get('processed')
    event_type_filter = request.GET.get('event_type')
    
    # Query base
    updates = ShipmentStatusUpdate.objects.all()
    
    # Applica filtri
    if status_filter:
        updates = updates.filter(new_status=status_filter)
    
    if processed_filter:
        processed = processed_filter.lower() == 'true'
        updates = updates.filter(processed=processed)
        
    if event_type_filter:
        updates = updates.filter(event_type=event_type_filter)
    
    # Limita a 10 record per default
    limit = int(request.GET.get('limit', 10))
    updates = updates[:limit]
    
    # Conteggio per status
    status_counts = {}
    for status, _ in ShipmentStatusUpdate.STATUS_CHOICES:
        status_counts[status] = ShipmentStatusUpdate.objects.filter(new_status=status).count()
    
    # Conteggio per tipo evento
    event_counts = {}
    for event_type, _ in ShipmentStatusUpdate.EVENT_TYPES:
        event_counts[event_type] = ShipmentStatusUpdate.objects.filter(event_type=event_type).count()
    
    # Informazioni sull'ambiente per Railway
    is_railway = bool(os.environ.get('RAILWAY_STATIC_URL') or os.environ.get('RAILWAY_PUBLIC_DOMAIN'))
    railway_url = None
    if is_railway:
        domain = os.environ.get('RAILWAY_STATIC_URL') or os.environ.get('RAILWAY_PUBLIC_DOMAIN')
        if domain:
            railway_url = f"https://{domain}" if not domain.startswith('http') else domain
    
    # Ottieni lista dei webhook configurati
    webhook_listing = None
    try:
        result = list_webhooks()
        webhook_listing = result.get('output', 'Nessuna informazione disponibile sui webhook.')
    except Exception as e:
        webhook_listing = f"Errore nel recupero dei webhook: {str(e)}"
    
    context = {
        'updates': updates,
        'status_choices': ShipmentStatusUpdate.STATUS_CHOICES,
        'event_choices': ShipmentStatusUpdate.EVENT_TYPES,
        'status_counts': status_counts,
        'event_counts': event_counts,
        'current_status': status_filter,
        'current_processed': processed_filter,
        'current_event_type': event_type_filter,
        'total_updates': ShipmentStatusUpdate.objects.count(),
        'unprocessed_count': ShipmentStatusUpdate.objects.filter(processed=False).count(),
        'is_railway': is_railway,
        'railway_url': railway_url,
        'webhook_listing': webhook_listing,
        'title': 'Aggiornamenti stato spedizioni'
    }
    
    return render(request, 'prep_management/shipment_updates.html', context)

def manage_webhooks(request):
    """
    View per gestire i webhook di Prep Business.
    Permette di elencare, creare, eliminare e testare i webhook.
    """
    message = None
    output = None
    webhook_listing = None
    
    # Azioni sui webhook
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'list':
            result = list_webhooks()
            output = result.get('output', '')
        
        elif action == 'create':
            url = request.POST.get('webhook_url')
            merchant_id = request.POST.get('merchant_id')
            if merchant_id:
                try:
                    merchant_id = int(merchant_id)
                except ValueError:
                    merchant_id = None
            
            result = create_webhook(url, merchant_id)
            output = result.get('output', '')
            message = "Webhook creato con successo" if result.get('success') else f"Errore: {result.get('error', 'Errore sconosciuto')}"
        
        elif action == 'update':
            webhook_id = request.POST.get('webhook_id')
            url = request.POST.get('webhook_url')
            merchant_id = request.POST.get('merchant_id')
            
            try:
                webhook_id = int(webhook_id)
                if merchant_id:
                    merchant_id = int(merchant_id)
            except ValueError:
                message = "ID webhook non valido"
            else:
                result = update_webhook(webhook_id, url, merchant_id)
                output = result.get('output', '')
                message = "Webhook aggiornato con successo" if result.get('success') else f"Errore: {result.get('error', 'Errore sconosciuto')}"
        
        elif action == 'delete':
            webhook_id = request.POST.get('webhook_id')
            merchant_id = request.POST.get('merchant_id')
            
            try:
                webhook_id = int(webhook_id)
                if merchant_id:
                    merchant_id = int(merchant_id)
            except ValueError:
                message = "ID webhook non valido"
            else:
                result = delete_webhook(webhook_id, merchant_id)
                output = result.get('output', '')
                message = "Webhook eliminato con successo" if result.get('success') else f"Errore: {result.get('error', 'Errore sconosciuto')}"
        
        elif action == 'test':
            webhook_id = request.POST.get('webhook_id')
            merchant_id = request.POST.get('merchant_id')
            
            try:
                if webhook_id:
                    webhook_id = int(webhook_id)
                if merchant_id:
                    merchant_id = int(merchant_id)
            except ValueError:
                message = "ID webhook non valido"
            else:
                result = test_webhook(webhook_id, merchant_id)
                output = result.get('output', '')
                message = "Test webhook completato" if result.get('success') else f"Errore: {result.get('error', 'Errore sconosciuto')}"
    
    # Recupera la lista dei webhook per visualizzarla
    try:
        result = list_webhooks()
        webhook_listing = result.get('output', '')
    except Exception as e:
        webhook_listing = f"Errore nell'elenco dei webhook: {str(e)}"
    
    # Determina l'URL corrente dell'applicazione
    import os
    is_railway = bool(os.environ.get('RAILWAY_STATIC_URL') or os.environ.get('RAILWAY_PUBLIC_DOMAIN'))
    webhook_url = None
    
    if is_railway:
        domain = os.environ.get('RAILWAY_STATIC_URL') or os.environ.get('RAILWAY_PUBLIC_DOMAIN')
        if domain:
            webhook_url = f"https://{domain}" if not domain.startswith('http') else domain
            webhook_url = f"{webhook_url.rstrip('/')}/prep_management/webhook/"
    else:
        webhook_url = f"{request.scheme}://{request.get_host()}/prep_management/webhook/"
    
    context = {
        'title': 'Gestione Webhook Prep Business',
        'message': message,
        'output': output,
        'webhook_listing': webhook_listing,
        'suggested_url': webhook_url,
        'is_railway': is_railway
    }
    
    return render(request, 'prep_management/manage_webhooks.html', context)

def push_outgoing_message(request):
    """
    Endpoint interno per aggiungere un messaggio in coda.
    """
    # Body: { "message_id": str, "parameters": {...} }
    data = json.loads(request.body)
    msg = OutgoingMessage.objects.create(
        message_id=data.get('message_id'),
        parameters=data.get('parameters', {})
    )
    return JsonResponse({'success': True, 'message': 'Messaggio aggiunto', 'id': msg.id})

@api_view(['GET', 'OPTIONS'])
def poll_outgoing_messages(request):
    """
    Poll API: restituisce i messaggi e li segna come consumati.
    Gestisce anche le richieste OPTIONS per CORS preflight.
    """
    if request.method == 'OPTIONS':
        response = Response()
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Credentials"] = "true"
        response["Access-Control-Allow-Headers"] = "*"
        response["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        return response
    now = timezone.now()
    # Rimuovi messaggi non consumati più vecchi di 2 ore
    OutgoingMessage.objects.filter(consumed=False, created_at__lt=now - timedelta(hours=2)).delete()
    # Rimuovi messaggi consumati da più di 10 secondi
    OutgoingMessage.objects.filter(consumed=True, consumed_at__lt=now - timedelta(seconds=10)).delete()
    # Preleva i nuovi messaggi non ancora consumati
    new_msgs = OutgoingMessage.objects.filter(consumed=False).order_by('created_at')
    # Segna come consumati
    new_msgs.update(consumed=True, consumed_at=now)
    # Tutti i messaggi validi sono quelli consumati negli ultimi 10 secondi
    valid_msgs = OutgoingMessage.objects.filter(consumed=True, consumed_at__gte=now - timedelta(seconds=10)).order_by('created_at')
    serializer = OutgoingMessageSerializer(valid_msgs, many=True)
    response = Response(serializer.data)
    response["Access-Control-Allow-Origin"] = "*"
    response["Access-Control-Allow-Credentials"] = "true"
    response["Access-Control-Allow-Headers"] = "*"
    response["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    return response

def search_shipments_by_products(request):
    # Initialize context with safe defaults
    merchants = get_merchants() 
    context_vars = {
        'keywords': '',
        'search_type': 'OR',
        'merchant_name': '',
        'shipment_type': '',
        'shipment_status': '',
        'max_results': 100, # Default int value
        'date_from': '',
        'date_to': '',
        'debug_page': 1, # Default int value
        'merchants': merchants,
        'title': 'Ricerca spedizioni per prodotti',
        'shipments': [],
        'error': None,
        'is_waiting': False,
        'partial_count': 0,
        'total_shipments_read': 0,  # Nuovo contatore per spedizioni lette
        'matching_shipments_count': 0  # Nuovo contatore per spedizioni corrispondenti
    }
    
    # Update context with actual GET parameters if present
    if request.GET:
        context_vars.update({
            'keywords': request.GET.get('keywords', ''),
            'search_type': request.GET.get('search_type', 'OR'),
            'merchant_name': request.GET.get('merchant_name', ''),
            'shipment_type': request.GET.get('shipment_type', ''),
            'shipment_status': request.GET.get('shipment_status', ''),
            'max_results': int(request.GET.get('max_results') or 100),
            'date_from': request.GET.get('date_from', ''),
            'date_to': request.GET.get('date_to', ''),
            'debug_page': int(request.GET.get('debug_page') or 1),
        })

    partial_count = 0 # Reset partial count for each request
    matching_shipments = [] # Initialize matching shipments list
    
    # Check if a search was actually triggered (e.g., by checking if merchant_name is present in GET)
    search_triggered = 'merchant_name' in request.GET
    logger.info(f"Search triggered: {search_triggered}, GET params: {dict(request.GET)}")

    if not search_triggered:
        # Just render the empty form if no search was triggered
        logger.info("No search triggered, rendering empty form")
        return render(request, 'prep_management/search_shipments.html', context_vars)

    # Start processing the search request
    try:
        logger.info(f"TUTTI I PARAMETRI GET: {dict(request.GET)}")
        
        # --- Get parameters safely from updated context_vars ---
        keywords_str = context_vars['keywords']
        keywords = [k.strip() for k in keywords_str.split(',') if k.strip()]
        search_type = context_vars['search_type']
        merchant_name = context_vars['merchant_name'].strip()
        shipment_type_filter = context_vars['shipment_type'].strip()
        shipment_status_filter = context_vars['shipment_status'].strip()
        date_from = context_vars['date_from'].strip()
        date_to = context_vars['date_to'].strip()
        max_results = context_vars['max_results']
        debug_page_start = context_vars['debug_page']
        # -----------------------------------------------------

        logger.info(f"Parametri di ricerca: keywords={keywords}, search_type={search_type}, merchant_name={merchant_name}, shipment_type={shipment_type_filter}, shipment_status={shipment_status_filter}, max_results={max_results}, date_from={date_from}, date_to={date_to}, debug_page={debug_page_start}")

        merchant_id = None
        if merchant_name:
            merchant = next((m for m in merchants if m['name'].lower() == merchant_name.lower()), None)
            if merchant:
                merchant_id = merchant['id']
                logger.info(f"Merchant trovato: {merchant_name} (ID: {merchant_id})")
            else:
                logger.warning(f"Merchant non trovato: {merchant_name}")
                context_vars['error'] = f'Merchant \'{merchant_name}\' non trovato'
                return render(request, 'prep_management/search_shipments.html', context_vars)
        else: # No merchant name provided in GET request
             logger.warning("Nessun merchant selezionato")
             context_vars['error'] = 'Seleziona un merchant per avviare la ricerca.'
             return render(request, 'prep_management/search_shipments.html', context_vars)

        # --- Start the potentially long process ---
        context_vars['is_waiting'] = True
        logger.info("Inizio recupero spedizioni...")

        company_domain = PREP_BUSINESS_API_URL.split('//')[-1].split('/')[0]
        client = PrepBusinessClient(PREP_BUSINESS_API_KEY, company_domain)

        # --- Build Query ---
        q_parts = []
        use_archived_endpoint = shipment_status_filter == 'archived' and (not shipment_type_filter or shipment_type_filter == 'outbound')
        if date_from:
            q_parts.append(f'created_at:>="{date_from}"')
        if date_to:
            q_parts.append(f'created_at<="{date_to}"')
        q_parts.append('sort:created_at:desc')
        q_query = ' AND '.join(q_parts) if q_parts else None
        logger.info(f"QUERY AVANZATA Q (per recupero spedizioni): {q_query}")

        # --- Retrieve Shipments (Outbound focused for now) ---
        retrieved_shipments_for_filtering = []
        if not shipment_type_filter or shipment_type_filter == 'outbound':
            outbound_api_shipments = []
            page = debug_page_start
            first_page_logged = False
            
            api_method_name = 'get_outbound_shipments'
            log_message_prefix = "outbound"
            if shipment_status_filter == 'archived':
                api_method_name = 'get_archived_outbound_shipments'
                log_message_prefix = "outbound archiviate"
            
            api_method = getattr(client, api_method_name)
            logger.info(f"Recupero spedizioni {log_message_prefix} per merchant {merchant_id} con filtro q: {q_query}")

            while True:
                if len(outbound_api_shipments) >= max_results: break
                # Always request 20 per page, as API seems limited anyway
                current_per_page = 20 

                retry_count = 0
                max_retries = 5
                api_response = None
                
                while retry_count < max_retries:
                    try:
                        logger.info(f"Tentativo {retry_count+1}/{max_retries} - Recupero pagina {page} delle spedizioni {log_message_prefix}, per_page={current_per_page}")
                        context_vars['partial_count'] = len(outbound_api_shipments) # Update count during wait
                        api_response = api_method(
                            merchant_id=merchant_id, per_page=current_per_page,
                            page=page, search_query=q_query
                        )
                        logger.info(f"Risposta API ricevuta per pagina {page}: {api_response}")
                        break 
                    except Exception as e_api:
                        error_str = str(e_api)
                        logger.error(f"Errore API durante il recupero spedizioni: {error_str}", exc_info=True)
                        if '502' in error_str or '429' in error_str:
                            wait_time = 5 * (2 ** retry_count)
                            logger.warning(f"Errore API ({error_str}) su pagina {page}. Retry tra {wait_time}s (tentativo {retry_count+1}/{max_retries})")
                            context_vars['error'] = f"Errore temporaneo API ({error_str}) pagina {page}. Attesa {wait_time}s..." # Temporary error message
                            time.sleep(wait_time)
                            retry_count += 1
                        else:
                            logger.error(f"Errore API non gestito durante il recupero spedizioni: {e_api}", exc_info=True)
                            context_vars['error'] = f"Errore API imprevisto durante recupero pagina {page}: {e_api}. Record letti: {len(outbound_api_shipments)}"
                            raise # Rilancia per il blocco try...except globale
                
                if retry_count >= max_retries:
                    logger.error(f"Superato numero massimo di retry per pagina {page} ({log_message_prefix}).")
                    context_vars['error'] = f"Errore API (502/429) persistente dopo {max_retries} tentativi sulla pagina {page}. Record letti: {len(outbound_api_shipments)}"
                    break 
                
                if not api_response or not hasattr(api_response, 'data') or not api_response.data:
                    logger.info(f"Nessun dato o risposta API non valida per pagina {page} ({log_message_prefix}). Interruzione paginazione.")
                    break

                current_shipments_from_api = api_response.data
                logger.info(f"Ricevute {len(current_shipments_from_api)} spedizioni dalla pagina {page}")
                outbound_api_shipments.extend(current_shipments_from_api)
                partial_count = len(outbound_api_shipments)
                context_vars['partial_count'] = partial_count # Update final count for this stage

                if not first_page_logged:
                    # Simplified logging to avoid potential errors with complex getattr/str
                    logger.info(f"DEBUG URL chiamata: {api_method_name}?merchant_id={merchant_id}&per_page={current_per_page}&page={page}&search_query={q_query}")
                    try:
                       raw_resp_str = str(api_response)[:2000] # Limit length
                       logger.info(f"DEBUG Risposta grezza (prime 2000 char): {raw_resp_str}")
                    except Exception as log_e:
                       logger.warning(f"Impossibile loggare risposta grezza: {log_e}")
                    first_page_logged = True
                
                api_current_page = getattr(api_response, 'current_page', page)
                api_last_page = getattr(api_response, 'last_page', page)
                logger.info(f"Pagina {api_current_page}/{api_last_page} ({log_message_prefix}), {len(current_shipments_from_api)} spedizioni ricevute, accumulate: {partial_count}")

                if api_current_page >= api_last_page or len(outbound_api_shipments) >= max_results:
                    break
                
                page += 1
                logger.info(f"Attesa di 3 secondi prima della prossima pagina...")
                context_vars['error'] = None # Clear temporary error message before sleep
                time.sleep(3)

            logger.info(f"Totale spedizioni {log_message_prefix} recuperate prima del filtraggio per item: {len(outbound_api_shipments)}")
            for ship_data in outbound_api_shipments:
                 status = ship_data.status
                 if isinstance(status, Enum): status = status.value 
                 if status == 'closed': status = 'archived'
                 retrieved_shipments_for_filtering.append({
                     'id': ship_data.id, 'name': ship_data.name, 
                     'status': status, 'type': 'outbound'
                 })
        
        # Aggiorna il contatore delle spedizioni lette
        context_vars['total_shipments_read'] = len(retrieved_shipments_for_filtering)
        
        # --- Filter by item keywords ---
        logger.info(f"Totale spedizioni da filtrare per item (inbound+outbound): {len(retrieved_shipments_for_filtering)}")
        final_error_message = context_vars.get('error') # Preserve API error if any

        if retrieved_shipments_for_filtering and keywords: # Only filter if keywords provided
            logger.info(f"Inizio filtraggio per prodotti/titolo spedizione ({keywords_str}) su {len(retrieved_shipments_for_filtering)} spedizioni.")
            for shipment_summary in retrieved_shipments_for_filtering:
                try:
                    shipment_id = shipment_summary['id']
                    shipment_type = shipment_summary['type']
                    logger.debug(f"Recupero dettagli per spedizione {shipment_id} (tipo: {shipment_type})")

                    # Recupera dettagli spedizione (serve per il titolo)
                    details = None
                    items_response = None
                    if shipment_type == 'inbound':
                        # details = client.get_inbound_shipment(shipment_id, merchant_id=merchant_id) # Se serve
                        items_response = client.get_inbound_shipment_items(shipment_id, merchant_id=merchant_id)
                    else:
                        details = client.get_outbound_shipment(shipment_id, merchant_id=merchant_id)
                        items_response = client.get_outbound_shipment_items(shipment_id, merchant_id=merchant_id)

                    # Determina il titolo della spedizione
                    shipment_title = ''
                    if details and hasattr(details, 'shipment') and hasattr(details.shipment, 'name'):
                        shipment_title = getattr(details.shipment, 'name', '').lower()
                    elif 'name' in shipment_summary:
                        shipment_title = shipment_summary['name'].lower()

                    # 1. Cerca la keyword nel titolo della spedizione
                    match_in_title = False
                    if search_type == 'AND':
                        match_in_title = all(k.lower() in shipment_title for k in keywords)
                    else:
                        match_in_title = any(k.lower() in shipment_title for k in keywords)

                    # 2. Se non trovata nel titolo, cerca nei prodotti
                    match_in_items = False
                    actual_items = items_response.items if hasattr(items_response, 'items') else []
                    current_matching_items = []
                    if not match_in_title and actual_items:
                        for item_detail in actual_items:
                            item_name_to_search = ""
                            if shipment_type == 'inbound':
                                item_name_to_search = getattr(item_detail, 'name', '').lower()
                            else:
                                if hasattr(item_detail, 'item') and hasattr(item_detail.item, 'title'):
                                    item_name_to_search = getattr(item_detail.item, 'title', '').lower()
                            if not item_name_to_search:
                                continue
                            if search_type == 'AND':
                                match = all(k.lower() in item_name_to_search for k in keywords)
                            else:
                                match = any(k.lower() in item_name_to_search for k in keywords)
                            if match:
                                current_matching_items.append(item_detail)
                        if current_matching_items:
                            match_in_items = True

                    # Se trovata nel titolo O in almeno un prodotto, aggiungi la spedizione
                    if match_in_title or match_in_items:
                        shipment_obj_to_display = details.shipment if details and hasattr(details, 'shipment') else shipment_summary
                        matching_shipments.append({
                            'shipment': shipment_obj_to_display,
                            'matching_items': current_matching_items if match_in_items else [],
                            'type': shipment_type
                        })

                except Exception as e_detail:
                    logger.error(f"Errore nel recupero dettagli/item per spedizione {shipment_summary.get('id', 'N/A')}: {e_detail}")
                    if not final_error_message:
                        final_error_message = (final_error_message or "") + f"\nAttenzione: Errore recupero dettagli spedizione {shipment_summary.get('id', 'N/A')}. Risultati potrebbero essere incompleti."
        elif retrieved_shipments_for_filtering and not keywords:
            logger.info("Nessuna keyword specificata, mostro tutte le spedizioni recuperate.")
            for shipment_summary in retrieved_shipments_for_filtering:
                matching_shipments.append({
                    'shipment': shipment_summary,
                    'matching_items': [],
                    'type': shipment_summary['type']
                })


        # --- Final Rendering ---
        context_vars['is_waiting'] = False
        context_vars['shipments'] = matching_shipments
        context_vars['partial_count'] = partial_count 
        context_vars['error'] = final_error_message # Set final error message
        context_vars['matching_shipments_count'] = len(matching_shipments)  # Aggiorna il contatore delle spedizioni corrispondenti

        logger.info(f"Rendering pagina con {len(matching_shipments)} spedizioni finali. Error: {context_vars.get('error')}")
        return render(request, 'prep_management/search_shipments.html', context_vars)

    except Exception as e_global:
        logger.error(f"ERRORE GLOBALE NELLA VIEW search_shipments_by_products: {e_global}", exc_info=True)
        context_vars['error'] = f"Si è verificato un errore imprevisto durante la ricerca: {e_global}. Record letti prima dell\'errore: {partial_count}"
        context_vars['is_waiting'] = False
        context_vars['shipments'] = matching_shipments # Show partial results if any
        context_vars['partial_count'] = partial_count
        return render(request, 'prep_management/search_shipments.html', context_vars)
