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
from .models import ShipmentStatusUpdate, OutgoingMessage, SearchResultItem, IncomingMessage
from .serializers import OutgoingMessageSerializer, IncomingMessageSerializer
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
import uuid
from libs.prepbusiness.webhook_manager import list_webhooks, create_webhook, delete_webhook, test_webhook, update_webhook
from libs.prepbusiness.webhook_processor import WebhookProcessor
from libs.prepbusiness.webhook_receiver import WebhookReceiver
from .event_handlers import WebhookEventProcessor
from django.utils import timezone
from datetime import timedelta
from libs.prepbusiness.client import PrepBusinessClient
from libs.config import PREP_BUSINESS_API_KEY, PREP_BUSINESS_API_URL
from enum import Enum
from functools import wraps
from typing import Optional, Dict, Any, List
from django.core.cache import cache
from libs.prepbusiness.models import (
    OutboundShipmentResponse,
    OutboundShipmentItemsResponse,
    InboundShipmentResponse,
    ShipmentItemsResponse
)
from .tasks import process_shipment_batch, echo_task, process_shipment_search_task
from .utils.extractors import extract_product_info_from_dict
from .utils.clients import get_client
# from django.contrib.auth.decorators import login_required

from libs.config import (
    PREP_BUSINESS_API_URL,
    PREP_BUSINESS_API_KEY,
    PREP_BUSINESS_API_TIMEOUT,
    PREP_BUSINESS_MAX_RETRIES,
    PREP_BUSINESS_RETRY_BACKOFF
)
import re
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage

logger = logging.getLogger('prep_management')
logging.getLogger("httpx").setLevel(logging.DEBUG)

def truncate_log_message(message_obj: Any, max_len: int = 1200, placeholder: str = "....[PORZIONE CANCELLATA]....") -> str:
    """Tronca la rappresentazione stringa di un oggetto per il logging."""
    try:
        s = str(message_obj)
        if len(s) > max_len:
            half_len = (max_len - len(placeholder)) // 2
            if half_len < 10: # Ensure we have some context even if placeholder is long
                return s[:max_len] + "..."
            return f"{s[:half_len]}{placeholder}{s[-half_len:]}"
        return s
    except Exception:
        return "[Impossibile convertire oggetto in stringa per il log]"

def index(request):
    # Definisce le app disponibili con informazioni e link
    available_apps = [
        {
            'name': 'Verifica Foto Prodotti',
            'description': 'Tramite l\'EAN o l\'FNSKU del prodotto, verifica se è stata gia inviata la foto o meno.',
            'url': 'https://apppc.fbaprepcenteritaly.com/picture_check/',
            'icon': 'fas fa-camera',
            'color': 'primary',
            'status': 'attiva'
        },
        {
            'name': 'Etichette Pallet',
            'description': 'Generatore di etichette di spedizione per i pallet destinati ad Amazon. Crea PDF stampabili con tutte le informazioni di spedizione necessarie.',
            'url': '/pallet_label/',
            'icon': 'fas fa-shipping-fast',
            'color': 'success',
            'status': 'attiva'
        }
    ]
    
    context = {
        'available_apps': available_apps,
        'total_apps': len(available_apps)
    }
    
    return render(request, 'prep_management/index.html', context)

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
            
            # Utilizziamo PrepBusinessClient invece di chiamate dirette con requests
            company_domain = PREP_BUSINESS_API_URL.split('//')[-1].split('/')[0]
            client = PrepBusinessClient(
                api_key=PREP_BUSINESS_API_KEY,
                company_domain=company_domain,
                timeout=PREP_BUSINESS_API_TIMEOUT
            )
            
            # Test di connessione all'endpoint merchants
            logger.info("Test connessione all'endpoint merchants usando PrepBusinessClient")
            merchants_response = client.get_merchants()
            
            # Converti la risposta nel formato atteso per la visualizzazione
            test_result = {
                'success': True,
                'status_code': 200,  # Assumiamo 200 se la chiamata non ha sollevato eccezioni
                'status_text': "OK",
                'headers': {"Content-Type": "application/json"},  # Minimale per UI
                'content': str(merchants_response)[:500] + ('...' if len(str(merchants_response)) > 500 else ''),
                'json': {
                    'data': [
                        {
                            'id': merchant.id,
                            'name': merchant.name,
                            'email': getattr(merchant, 'primaryEmail', 'N/A')
                        } 
                        for merchant in getattr(merchants_response, 'data', [])[:5]  # Mostra solo i primi 5
                    ],
                    'count': len(getattr(merchants_response, 'data', []))
                }
            }
                
            logger.info(f"Test API completato con successo: {test_result['json']['count']} merchants trovati")
            
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

def retry_on_error(max_retries=3, delay=1, backoff=2):
    """
    Decorator per implementare retry logic con exponential backoff.
    
    Args:
        max_retries: Numero massimo di tentativi
        delay: Delay iniziale in secondi
        backoff: Fattore di moltiplicazione per il delay
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(f"Tentativo {attempt + 1}/{max_retries} fallito: {str(e)}")
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"Tutti i tentativi falliti dopo {max_retries} tentativi")
                        raise last_exception
            
            raise last_exception
        return wrapper
    return decorator

@retry_on_error(max_retries=3, delay=2, backoff=2)
def get_shipment_details(client: PrepBusinessClient, shipment_id: int, shipment_type: str, merchant_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Recupera i dettagli di una spedizione con retry logic. API reale, log dettagliati.
    """
    logger.info(f"[API get_shipment_details] INIZIO: shipment_id={shipment_id}, tipo={shipment_type}, merchant={merchant_id}")
    response_obj = None
    dumped_response = None
    try:
        if shipment_type == 'inbound':
            logger.info(f"[API get_shipment_details] Chiamo client.get_inbound_shipment({shipment_id}, merchant_id={merchant_id})")
            response_obj = client.get_inbound_shipment(shipment_id, merchant_id=merchant_id)
        else:
            logger.info(f"[API get_shipment_details] Chiamo client.get_outbound_shipment({shipment_id}, merchant_id={merchant_id})")
            response_obj = client.get_outbound_shipment(shipment_id, merchant_id=merchant_id)
        
        resp_str = str(response_obj)
        if len(resp_str) > 500:
            logger.info(f"[API get_shipment_details] Risposta Pydantic (troncata): {resp_str[:250]} ... {resp_str[-250:]}")
        else:
            logger.info(f"[API get_shipment_details] Risposta Pydantic: {resp_str}")
            
        # Isolo model_dump() in un try-except separato
        try:
            logger.info(f"[API get_shipment_details] Prima di model_dump() per shipment_id={shipment_id}")
            dumped_response = response_obj.model_dump()
            logger.info(f"[API get_shipment_details] Dopo model_dump() per shipment_id={shipment_id}. Risultato (troncato): {truncate_log_message(dumped_response)}")
        except Exception as e_dump:
            logger.error(f"[API get_shipment_details] ERRORE durante model_dump() per shipment_id={shipment_id}: {e_dump}")
            logger.error(f"[API get_shipment_details] Traceback model_dump(): {traceback.format_exc()}")
            logger.error(f"[API get_shipment_details] Oggetto response_obj al momento dell'errore model_dump(): {truncate_log_message(response_obj)}")
            raise # Rilancio l'eccezione per farla gestire dal try-except esterno
            
        logger.info(f"[API get_shipment_details] FINE OK: shipment_id={shipment_id}, tipo={shipment_type}")
        return dumped_response
        
    except Exception as e:
        logger.error(f"[API get_shipment_details] ERRORE (esterno a model_dump): {e} per shipment_id={shipment_id}")
        logger.error(f"[API get_shipment_details] Traceback (esterno a model_dump): {traceback.format_exc()}")
        if response_obj: # Logga l'oggetto Pydantic se disponibile, anche se model_dump è fallito o non è stato raggiunto
            logger.error(f"[API get_shipment_details] Oggetto response_obj (Pydantic) al momento dell'errore esterno: {truncate_log_message(response_obj)}")
        raise

@retry_on_error(max_retries=3, delay=2, backoff=2)
def get_shipment_items(client: PrepBusinessClient, shipment_id: int, shipment_type: str, merchant_id: Optional[int] = None) -> Dict[str, Any]:
    """
    MOCK: Restituisce sempre dati fittizi per gli items spedizione, senza chiamare l'API reale.
    """
    logger.info(f"[MOCK get_shipment_items] Restituisco dati mock per shipment_id={shipment_id}, tipo={shipment_type}, merchant={merchant_id}")
    if shipment_type == 'inbound':
        items = []
        for i in range(1, 4):
            title = f"Prodotto inbound {i}"
            if i == 2 and (shipment_id % 2 == 0):
                title = f"Singer Prodotto inbound {i}"
            item = {
                'id': shipment_id * 100 + i,
                'name': title,
                'sku': f"SKU-IN-{shipment_id}-{i}",
                'asin': f"ASIN{shipment_id}{i}",
                'fnsku': f"FNSKU{shipment_id}{i}",
                'quantity': 10 * i
            }
            items.append(item)
        mock_response = {'items': items, 'total': len(items)}
    else:
        items = []
        for i in range(1, 4):
            title = f"Prodotto outbound {i}"
            if i == 1 and (shipment_id % 2 == 1):
                title = f"Singer Prodotto outbound {i}"
            item = {
                'id': shipment_id * 100 + i,
                'quantity': 5 * i,
                'item': {
                    'id': shipment_id * 1000 + i,
                    'title': title,
                    'merchant_sku': f"SKU-OUT-{shipment_id}-{i}",
                    'asin': f"ASIN{shipment_id}{i}",
                    'fnsku': f"FNSKU{shipment_id}{i}"
                }
            }
            items.append(item)
        mock_response = {'items': items, 'total': len(items)}
    return mock_response

@csrf_exempt
# @login_required
def search_shipments_by_products(request):
    # Assicurati che il logger sia a livello DEBUG per vedere questi messaggi
    logger.debug(f"[search_shipments_by_products DEBUG] --- INIZIO RICHIESTA ---")
    # Registra il tempo di inizio per evitare timeout
    import time
    start_time = time.time()
    # Imposta una soglia di sicurezza (30 secondi) per evitare il timeout di 60 secondi
    MAX_EXECUTION_TIME = 30
    
    logger.info(f"[search_shipments_by_products] INIZIO - method={request.method}, POST={request.POST.dict()}, GET={request.GET.dict()}")
    
    merchants = get_merchants()
    context = {
        'merchants': merchants,
        'merchant_id': request.POST.get('merchant_id') or request.GET.get('merchant_id'),
        'shipment_type': request.POST.get('shipment_type') or request.GET.get('shipment_type', ''),
        'shipment_status': request.POST.get('shipment_status') or request.GET.get('shipment_status', ''),
        'keywords': request.POST.get('keywords') or request.GET.get('keywords', ''),
        'search_type': request.POST.get('search_type') or request.GET.get('search_type', 'OR'),
        'max_shipments': request.POST.get('max_shipments') or request.GET.get('max_shipments', 20),
    }

    if request.method == 'GET':
        logger.info(f"[search_shipments_by_products] GET polling - search_id={request.GET.get('search_id')}, page={request.GET.get('page')}")
        search_id_get = request.GET.get('search_id')
        # ... (logica GET esistente) ...
        # Se la ricerca è finita e non ci sono risultati, mostra subito no_results
        if search_id_get and cache.get(f"{search_id_get}_done") and not SearchResultItem.objects.filter(search_id=search_id_get).exists():
            logger.debug(f"[search_shipments_by_products DEBUG] GET: Ricerca {search_id_get} completata, nessun risultato trovato in DB.")
            return render(request, 'prep_management/search_shipments.html', {
                'results': [], 'is_waiting': False, 'search_id': search_id_get,
                'error': 'Nessun risultato trovato per le parole chiave.', **context
            })
        # ... (altra logica GET esistente) ...
        # Aggiungi un return per il caso base GET senza search_id o se non è ancora "done"
        if not search_id_get:
             logger.debug(f"[search_shipments_by_products DEBUG] GET: Nessun search_id fornito, mostro form base.")
             return render(request, 'prep_management/search_shipments.html', {'results': [], 'is_waiting': False, **context})
        # Qui gestisci il rendering dei risultati parziali o finali se search_id è presente
        # (La logica di paginazione esistente dovrebbe andare qui)
        try:
            # Log dettagliato prima di cercare i risultati nel DB
            logger.info(f"[VIEW_GET] Cerco risultati per search_id={search_id_get} nel database")
            
            results_from_db = SearchResultItem.objects.filter(search_id=search_id_get).order_by('-id')
            result_count = results_from_db.count()
            logger.info(f"[VIEW_GET] Trovati {result_count} risultati nel database per search_id={search_id_get}")
            
            # Log di alcuni risultati se presenti
            if result_count > 0:
                sample_results = results_from_db[:3]
                for idx, item in enumerate(sample_results):
                    logger.info(f"[VIEW_GET] Risultato {idx+1}: shipment_name={item.shipment_name}, title='{item.product_title}', sku={item.product_sku}")
            
            # Log dettagliato dello stato
            cache_done = cache.get(f"{search_id_get}_done")
            results_exist = results_from_db.exists()
            logger.info(f"[VIEW_GET] *** STATO COMPLETO search_id={search_id_get} ***")
            logger.info(f"[VIEW_GET] cache_done = {cache_done}")
            logger.info(f"[VIEW_GET] results_exist = {results_exist}")
            logger.info(f"[VIEW_GET] results_count = {result_count}")
            
            # Modifica: is_still_processing è True solo se il task non è finito E non ci sono risultati
            is_still_processing = not cache_done and not results_exist
            
            # Se il task è finito ma non ci sono risultati, imposta is_still_processing a False
            if cache_done and not results_exist:
                is_still_processing = False
                logger.info(f"[VIEW_GET] Task finito ma nessun risultato trovato. is_still_processing=False")
            
            # Log finale dello stato
            logger.info(f"[VIEW_GET] - is_still_processing = {is_still_processing}")
            logger.info(f"[VIEW_GET] - total_to_analyze = {cache.get(f'search_{search_id_get}_total_to_analyze', 0)}")
            logger.info(f"[VIEW_GET] - matched_count = {result_count}")

            # --- AGGIUNTA: Verifica che i risultati vengano passati correttamente al template ---
            paginator = Paginator(results_from_db, 10)
            page_number = request.GET.get('page', 1)
            try:
                page_obj = paginator.page(page_number)
                logger.info(f"[VIEW_GET] Paginazione: pagina {page_number} di {paginator.num_pages}, oggetti in pagina: {len(page_obj.object_list)}")
            except (PageNotAnInteger, EmptyPage):
                page_obj = paginator.page(1)
                logger.info(f"[VIEW_GET] Fallback alla pagina 1. Oggetti in pagina: {len(page_obj.object_list)}")

            # --- AGGIUNTA: calcolo avanzamento ---
            total_to_analyze = cache.get(f"search_{search_id_get}_total_to_analyze", 0)
            matched_count_from_db = results_from_db.count()
            polling_message = None
            if is_still_processing and total_to_analyze > 0:
                polling_message = f"Trovate {matched_count_from_db} spedizioni su {total_to_analyze} analizzate finora."
                logger.info(f"[VIEW_GET] polling_message calcolato: {polling_message}")

            logger.info(f"[VIEW_GET] Rendering risultati per search_id {search_id_get}, pagina {page_number}. In attesa: {is_still_processing}")
            
            # Creazione del contesto per il template
            template_context = {
                'results': page_obj, 
                'is_waiting': is_still_processing, 
                'search_id': search_id_get,
                'polling_message': polling_message,
                'total_to_analyze': total_to_analyze,
                'matched_count': matched_count_from_db,
                **context
            }
            
            # Log del contesto passato al template
            logger.info(f"[VIEW_GET] Contesto template: results={len(page_obj.object_list) if hasattr(page_obj, 'object_list') else 'None'}, is_waiting={is_still_processing}")
            
            return render(request, 'prep_management/search_shipments.html', template_context)
        except Exception as e_get_render:
            logger.error(f"[search_shipments_by_products DEBUG] GET: Errore rendering risultati: {e_get_render}")
            return render(request, 'prep_management/search_shipments.html', {
                'error': str(e_get_render), 'is_waiting': False, **context
            })


    if request.method == 'POST':
        logger.debug(f"[VIEW_POST] --- INIZIO LOGICA POST ---")
        search_terms = request.POST.get('keywords', '').strip()
        if not search_terms:
            logger.info("[search_shipments_by_products] Nessun termine di ricerca fornito")
            return JsonResponse({'error': 'Nessun termine di ricerca fornito'}, status=400)
        merchant_id = request.POST.get('merchant_id')
        shipment_status = request.POST.get('shipment_status', '')
        max_shipments_to_analyze = int(request.POST.get('max_shipments', 20))
        search_id = str(uuid.uuid4())
        cache.delete(f"{search_id}_done")
        # Lancia il task Celery asincrono
        process_shipment_search_task.delay(
            search_id,
            search_terms,
            merchant_id,
            shipment_status,
            max_shipments_to_analyze
        )
        logger.info(f"[VIEW_POST] Task Celery process_shipment_search_task lanciato per search_id={search_id}")
        return JsonResponse({
            'status': 'processing',
            'search_id': search_id,
            'message': 'Ricerca avviata, i risultati saranno disponibili a breve.'
        })

    # Ritorno per GET non gestito esplicitamente sopra (dovrebbe essere coperto dalla logica GET iniziale)
    logger.debug(f"[search_shipments_by_products DEBUG] Richiesta GET non POST, rendering form base o risultati esistenti.")
    return render(request, 'prep_management/search_shipments.html', context)

def enqueue_box_services_request(payload: dict):
    """
    Salva un messaggio di tipo BOX_SERVICES_REQUEST nella coda OutgoingMessage.
    """
    from .models import OutgoingMessage
    OutgoingMessage.objects.create(
        message_id='BOX_SERVICES_REQUEST',
        parameters=payload
    )

# Esempio di utilizzo (da inserire dove serve, ad esempio nel gestore webhook):
# webhook_data = WebhookProcessor.parse_payload(request.body)
# box_services_payload = generate_box_services_request(webhook_data)
# enqueue_box_services_request(box_services_payload)

@csrf_exempt
@api_view(['POST', 'OPTIONS'])
def receive_extension_message(request):
    """
    Endpoint per ricevere messaggi dall'estensione Chrome verso l'app.
    L'estensione invia POST con i dati del messaggio.
    """
    if request.method == 'OPTIONS':
        response = Response()
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Credentials"] = "true"
        response["Access-Control-Allow-Headers"] = "*"
        response["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        return response
    
    try:
        # Estrai i dati dal payload
        data = request.data if hasattr(request, 'data') else json.loads(request.body)
        
        # Crea il messaggio in entrata
        incoming_msg = IncomingMessage.objects.create(
            message_type=data.get('message_type', 'USER_RESPONSE'),
            payload=data.get('payload', {}),
            session_id=data.get('session_id')
        )
        
        logger.info(f"Messaggio ricevuto dall'estensione: {incoming_msg.message_type} (session: {incoming_msg.session_id})")
        
        # Processa il messaggio se necessario
        process_result = _process_incoming_message(incoming_msg)
        
        response = Response({
            'success': True, 
            'message': 'Messaggio ricevuto',
            'id': incoming_msg.id,
            'process_result': process_result
        })
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Credentials"] = "true"
        response["Access-Control-Allow-Headers"] = "*"
        response["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        return response
        
    except Exception as e:
        logger.error(f"Errore nella ricezione messaggio dall'estensione: {str(e)}")
        response = Response({
            'success': False, 
            'error': str(e)
        }, status=400)
        response["Access-Control-Allow-Origin"] = "*"
        return response

@api_view(['GET', 'OPTIONS'])
def wait_for_extension_response(request):
    """
    Endpoint per attendere una risposta dall'estensione per una sessione specifica.
    Il backend fa polling solo quando attende una risposta specifica.
    
    Parametri:
    - session_id: ID della sessione per cui attendere la risposta
    - timeout: Timeout in secondi (default: 30)
    - message_type: Tipo di messaggio atteso (opzionale)
    """
    if request.method == 'OPTIONS':
        response = Response()
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Credentials"] = "true"
        response["Access-Control-Allow-Headers"] = "*"
        response["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        return response
    
    session_id = request.GET.get('session_id')
    timeout = int(request.GET.get('timeout', 30))
    expected_message_type = request.GET.get('message_type')
    
    if not session_id:
        return Response({'success': False, 'error': 'session_id richiesto'}, status=400)
    
    import time
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        # Cerca messaggi per questa sessione
        query = IncomingMessage.objects.filter(session_id=session_id, processed=False)
        
        if expected_message_type:
            query = query.filter(message_type=expected_message_type)
        
        messages = query.order_by('created_at')
        
        if messages.exists():
            # Marca i messaggi come processati
            message_ids = list(messages.values_list('id', flat=True))
            IncomingMessage.objects.filter(id__in=message_ids).update(
                processed=True,
                processed_at=timezone.now()
            )
            
            # Serializza e restituisci i messaggi
            serializer = IncomingMessageSerializer(messages, many=True)
            
            logger.info(f"Risposta ricevuta per sessione {session_id}: {len(messages)} messaggi")
            
            response = Response({
                'success': True,
                'messages': serializer.data,
                'session_id': session_id
            })
            response["Access-Control-Allow-Origin"] = "*"
            return response
        
        # Attendi un po' prima del prossimo controllo
        time.sleep(0.5)
    
    # Timeout raggiunto
    logger.warning(f"Timeout raggiunto per sessione {session_id}")
    response = Response({
        'success': False,
        'error': 'timeout',
        'session_id': session_id
    })
    response["Access-Control-Allow-Origin"] = "*"
    return response

def _process_incoming_message(incoming_msg: IncomingMessage) -> dict:
    """
    Processa un messaggio ricevuto dall'estensione.
    
    Args:
        incoming_msg: Il messaggio da processare
        
    Returns:
        Dict con il risultato dell'elaborazione
    """
    try:
        message_type = incoming_msg.message_type
        payload = incoming_msg.payload or {}
        
        result = {'processed': True, 'message': 'Messaggio elaborato'}
        
        if message_type == 'USER_RESPONSE':
            # Elabora risposta utente
            user_action = payload.get('action')
            if user_action:
                result['user_action'] = user_action
                logger.info(f"Azione utente ricevuta: {user_action}")
        
        elif message_type == 'ACTION_COMPLETED':
            # Elabora azione completata
            action_result = payload.get('result')
            if action_result:
                result['action_result'] = action_result
                logger.info(f"Azione completata: {action_result}")
        
        elif message_type == 'ERROR_REPORT':
            # Elabora segnalazione errore
            error_details = payload.get('error')
            if error_details:
                result['error_details'] = error_details
                logger.error(f"Errore segnalato dall'estensione: {error_details}")
        
        # Salva il risultato dell'elaborazione
        incoming_msg.process_result = result
        incoming_msg.save()
        
        return result
        
    except Exception as e:
        logger.error(f"Errore nell'elaborazione del messaggio {incoming_msg.id}: {str(e)}")
        error_result = {'processed': False, 'error': str(e)}
        incoming_msg.process_result = error_result
        incoming_msg.save()
        return error_result

def test_outbound_without_inbound(request):
    """
    Endpoint di test per verificare la funzionalità OUTBOUND_WITHOUT_INBOUND.
    Simula un webhook outbound_shipment.created e verifica che il messaggio venga prodotto.
    """
    from .event_handlers import WebhookEventProcessor
    from .models import ShipmentStatusUpdate
    
    # Simula un payload di webhook per outbound_shipment.created
    test_payload = {
        'data': {
            'id': 12345,
            'name': 'TEST_OUTBOUND_SPEDIZIONE_SENZA_INBOUND',
            'status': 'created',
            'merchant_id': 100,
            'created_at': '2024-01-15T10:30:00Z'
        },
        'event_type': 'outbound_shipment.created',
        'merchant_id': 100
    }
    
    try:
        # Crea un record di test nel database
        shipment_update = ShipmentStatusUpdate(
            shipment_id=test_payload['data']['id'],
            event_type='outbound_shipment.created',
            entity_type='outbound_shipment',
            previous_status=None,
            new_status='created',
            merchant_id=test_payload['merchant_id'],
            merchant_name='Test Merchant',
            tracking_number=None,
            carrier=None,
            notes=f"Test per verificare OUTBOUND_WITHOUT_INBOUND - {timezone.now()}",
            payload=test_payload
        )
        shipment_update.save()
        
        # Elabora l'evento usando il processor
        processor = WebhookEventProcessor()
        result = processor.process_event(shipment_update.id)
        
        # Controlla se ci sono messaggi in uscita di tipo OUTBOUND_WITHOUT_INBOUND
        from .models import OutgoingMessage
        outbound_messages = OutgoingMessage.objects.filter(
            message_id='OUTBOUND_WITHOUT_INBOUND'
        ).order_by('-created_at')[:5]
        
        return JsonResponse({
            'status': 'success',
            'message': 'Test completato',
            'test_shipment_id': shipment_update.id,
            'processor_result': result,
            'outbound_messages_count': outbound_messages.count(),
            'latest_outbound_messages': [
                {
                    'id': msg.id,
                    'created_at': msg.created_at.isoformat(),
                    'sent': msg.sent,
                    'parameters': msg.parameters
                } for msg in outbound_messages
            ],
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.exception("Errore durante il test outbound without inbound")
        return JsonResponse({
            'status': 'error',
            'message': f'Errore durante il test: {str(e)}',
            'timestamp': timezone.now().isoformat()
        }, status=500)
