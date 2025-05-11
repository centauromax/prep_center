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
from .models import ShipmentStatusUpdate, OutgoingMessage, SearchResultItem
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
from .tasks import process_shipment_batch
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
            results_from_db = SearchResultItem.objects.filter(search_id=search_id_get).order_by('-created_at')
            is_still_processing = not cache.get(f"{search_id_get}_done") and not results_from_db.exists()
            
            paginator = Paginator(results_from_db, 10) # o context['max_shipments']
            page_number = request.GET.get('page', 1)
            try:
                page_obj = paginator.page(page_number)
            except (PageNotAnInteger, EmptyPage):
                page_obj = paginator.page(1)

            logger.debug(f"[search_shipments_by_products DEBUG] GET: Rendering risultati per search_id {search_id_get}, pagina {page_number}. In attesa: {is_still_processing}")
            return render(request, 'prep_management/search_shipments.html', {
                'results': page_obj, 'is_waiting': is_still_processing, 
                'search_id': search_id_get, **context
            })
        except Exception as e_get_render:
            logger.error(f"[search_shipments_by_products DEBUG] GET: Errore rendering risultati: {e_get_render}")
            return render(request, 'prep_management/search_shipments.html', {
                'error': str(e_get_render), 'is_waiting': False, **context
            })


    if request.method == 'POST':
        logger.debug(f"[search_shipments_by_products DEBUG] --- INIZIO LOGICA POST ---")
        search_terms = request.POST.get('keywords', '').strip()
        if not search_terms:
            logger.info("[search_shipments_by_products] Nessun termine di ricerca fornito")
            return JsonResponse({'error': 'Nessun termine di ricerca fornito'}, status=400)
        
        merchant_id = request.POST.get('merchant_id')
        if not merchant_id: # Tolto or request.GET.get('merchant_id') perchè il POST dovrebbe averlo
            logger.info("[search_shipments_by_products] Merchant ID non trovato nel POST")
            return JsonResponse({'error': 'Merchant ID non trovato'}, status=400)
        
        logger.info(f"[search_shipments_by_products] Parametri validi: merchant_id={merchant_id}, search_terms={search_terms}")
        search_id = str(uuid.uuid4())
        cache.delete(f"{search_id}_done") # Rimuovi flag precedente se esiste
        logger.debug(f"[search_shipments_by_products DEBUG] Generato search_id: {search_id}")

        shipment_status = request.POST.get('shipment_status', '') # Default a stringa vuota se non fornito
        logger.info(f"[search_shipments_by_products] Filtro stato spedizione richiesto: '{shipment_status}'")

        max_shipments_to_analyze = int(request.POST.get('max_shipments', 20))
        logger.debug(f"[search_shipments_by_products DEBUG] Massimo numero di spedizioni da analizzare: {max_shipments_to_analyze}")

        client = get_client()
        all_shipments_from_api = []
        current_page = 1
        shipments_processed_count = 0

        logger.debug(f"[search_shipments_by_products DEBUG] Inizio loop recupero spedizioni API...")
        while shipments_processed_count < max_shipments_to_analyze:
            logger.debug(f"[search_shipments_by_products DEBUG] Richiesta pagina {current_page} di spedizioni (max_per_page=20). Stato: '{shipment_status if shipment_status else 'aperte (default)'}'")
            
            shipments_page_response = None
            try:
                if shipment_status == 'archived':
                    logger.debug(f"[search_shipments_by_products DEBUG] Chiamo client.get_archived_outbound_shipments(merchant_id={merchant_id}, page={current_page}, per_page=20)")
                    shipments_page_response = client.get_archived_outbound_shipments(merchant_id=merchant_id, page=current_page, per_page=20)
                else: # 'open' o vuoto (default API per aperte)
                    logger.debug(f"[search_shipments_by_products DEBUG] Chiamo client.get_outbound_shipments(merchant_id={merchant_id}, page={current_page}, per_page=20)")
                    shipments_page_response = client.get_outbound_shipments(merchant_id=merchant_id, page=current_page, per_page=20)
                logger.debug(f"[search_shipments_by_products DEBUG] Risposta API pagina {current_page}: {shipments_page_response}")
            except Exception as e_api_call:
                logger.error(f"[search_shipments_by_products DEBUG] Errore chiamata API per pagina {current_page}: {e_api_call}")
                break # Esce dal loop se c'è un errore API

            if not shipments_page_response or not shipments_page_response.data:
                logger.debug(f"[search_shipments_by_products DEBUG] Nessuna spedizione dati in risposta per pagina {current_page} o fine delle spedizioni API.")
                break 
            
            all_shipments_from_api.extend(shipments_page_response.data)
            shipments_processed_count = len(all_shipments_from_api) # Aggiorna il conteggio totale
            logger.debug(f"[search_shipments_by_products DEBUG] Pagina {current_page} processata. Totale spedizioni recuperate finora: {shipments_processed_count} (target: {max_shipments_to_analyze})")

            if not shipments_page_response.next_page_url:
                logger.debug(f"[search_shipments_by_products DEBUG] API indica che non ci sono altre pagine.")
                break
            current_page += 1
        
        logger.debug(f"[search_shipments_by_products DEBUG] Loop API terminato. Totale spedizioni recuperate: {len(all_shipments_from_api)}")
        # Analizza solo fino a max_shipments_to_analyze, se ne abbiamo recuperate di più
        shipments_to_analyze_list = all_shipments_from_api[:max_shipments_to_analyze]
        logger.debug(f"[search_shipments_by_products DEBUG] Lista finale di spedizioni da analizzare (max {max_shipments_to_analyze}): {len(shipments_to_analyze_list)}")

        found_shipments_for_celery_batch = []
        keywords_list = [kw.strip().lower() for kw in search_terms.split(',') if kw.strip()]
        logger.debug(f"[search_shipments_by_products DEBUG] Keywords da cercare: {keywords_list}")

        if not shipments_to_analyze_list: # Se non ci sono proprio spedizioni dall'API
            logger.debug(f"[search_shipments_by_products DEBUG] Nessuna spedizione recuperata dall'API. Termino.")
            cache.set(f"{search_id}_done", True, timeout=600)
            return JsonResponse({
                'status': 'no_results', 
                'message': 'Nessuna spedizione disponibile dal provider per i criteri iniziali.', 
                'results': [], 'search_id': search_id
            }, status=200)

        for idx, shipment_obj in enumerate(shipments_to_analyze_list):
            logger.debug(f"[search_shipments_by_products DEBUG] --- Analisi Spedizione {idx+1}/{len(shipments_to_analyze_list)}: ID {getattr(shipment_obj, 'id', 'N/A')}, Nome: {getattr(shipment_obj, 'name', 'N/A')} ---")
            
            # Controllo diretto solo su nome della spedizione
            shipment_matched_directly = False
            shipment_name_for_check = str(getattr(shipment_obj, 'name', '')).lower()
            logger.debug(f"[search_shipments_by_products DEBUG] Controllo keywords {keywords_list} in Spedizione.name: '{shipment_name_for_check[:100]}...'")
            if any(kw in shipment_name_for_check for kw in keywords_list):
                logger.debug(f"[search_shipments_by_products DEBUG] Keyword TROVATA in Spedizione.name per spedizione ID {getattr(shipment_obj, 'id', 'N/A')} ({getattr(shipment_obj, 'name', 'N/A')}). Match diretto.")
                found_shipments_for_celery_batch.append(shipment_obj)
                shipment_matched_directly = True
            
            if shipment_matched_directly:
                logger.debug(f"[search_shipments_by_products DEBUG] Spedizione ID {getattr(shipment_obj, 'id', 'N/A')} ({getattr(shipment_obj, 'name', 'N/A')}) aggiunta per match diretto.")
                continue # Passa alla prossima spedizione

            logger.debug(f"[search_shipments_by_products DEBUG] Nessun match diretto per Spedizione ID {getattr(shipment_obj, 'id', 'N/A')} ({getattr(shipment_obj, 'name', 'N/A')}). Controllo gli items.")
            try:
                shipment_id_for_items = getattr(shipment_obj, 'id', None)
                if shipment_id_for_items is None:
                    logger.warning(f"[search_shipments_by_products DEBUG] Impossibile ottenere ID per la spedizione: {shipment_obj}")
                    continue

                logger.debug(f"[search_shipments_by_products DEBUG] Richiesta items per Spedizione ID {shipment_id_for_items} ({getattr(shipment_obj, 'name', 'N/A')})...")
                items_response_dict = client.get_outbound_shipment_items(shipment_id=shipment_id_for_items, merchant_id=merchant_id)
                # Assumendo che items_response_dict sia un dict come {'items': [...]}
                items_list = items_response_dict.get('items', []) if isinstance(items_response_dict, dict) else []
                logger.debug(f"[search_shipments_by_products DEBUG] Ricevuti {len(items_list)} items per Spedizione ID {shipment_id_for_items} ({getattr(shipment_obj, 'name', 'N/A')}).")

                item_matched = False
                for item_idx, item_data in enumerate(items_list):
                    item_name_to_check = ''
                    # Estrazione del nome dell'item (struttura può variare)
                    if isinstance(item_data, dict):
                        inner_item_info = item_data.get('item') # Struttura comune per outbound
                        if inner_item_info and isinstance(inner_item_info, dict):
                            item_name_to_check = str(inner_item_info.get('title', '')).lower()
                        else: # Fallback per inbound o altre strutture
                            item_name_to_check = str(item_data.get('name') or item_data.get('title') or '').lower()
                    elif hasattr(item_data, 'name'): # Oggetto con attributo 'name'
                         item_name_to_check = str(item_data.name).lower()
                    elif hasattr(item_data, 'title'): # Oggetto con attributo 'title'
                         item_name_to_check = str(item_data.title).lower()
                    
                    logger.debug(f"[search_shipments_by_products DEBUG]  Item {item_idx+1}/{len(items_list)} (Sped. {getattr(shipment_obj, 'name', 'N/A')}): Controllo keywords in nome item '{item_name_to_check[:100]}...'")
                    if any(kw in item_name_to_check for kw in keywords_list):
                        logger.debug(f"[search_shipments_by_products DEBUG]  Keyword TROVATA in item (Nome: {item_name_to_check[:50]}) ! Spedizione ID {shipment_id_for_items} ({getattr(shipment_obj, 'name', 'N/A')}) aggiunta.")
                        found_shipments_for_celery_batch.append(shipment_obj)
                        item_matched = True
                        break # Trovato un item, basta per questa spedizione
                
                if not item_matched:
                    logger.debug(f"[search_shipments_by_products DEBUG] Nessuna keyword trovata negli items della Spedizione ID {shipment_id_for_items}.")

            except Exception as e_items:
                logger.error(f"[search_shipments_by_products DEBUG] Errore durante recupero/analisi items per Spedizione ID {getattr(shipment_obj, 'id', 'N/A')}: {e_items}")
        
        logger.debug(f"[search_shipments_by_products DEBUG] Analisi keyword completata. Spedizioni totali trovate per Celery: {len(found_shipments_for_celery_batch)}")

        if not found_shipments_for_celery_batch:
            logger.info("[search_shipments_by_products] Nessuna spedizione trovata dopo filtro keyword su spedizioni e items.")
            cache.set(f"{search_id}_done", True, timeout=600) # Segna come completata
            return JsonResponse({
                'status': 'no_results', 
                'message': 'Nessuna spedizione trovata per le parole chiave dopo aver analizzato le spedizioni e i loro prodotti.', 
                'results': [], 'search_id': search_id
            }, status=200)

        logger.debug(f"[search_shipments_by_products DEBUG] Invio {len(found_shipments_for_celery_batch)} spedizioni ai task Celery.")
        # Split found shipments into batches for Celery
        # (la logica di batching esistente qui sotto va bene)
        # ... (logica batching e chiamata Celery esistente) ...
        batch_size = 10 # O leggi da form se vuoi renderlo configurabile
        shipment_batches_for_celery = [found_shipments_for_celery_batch[i:i + batch_size] for i in range(0, len(found_shipments_for_celery_batch), batch_size)]
        
        logger.debug(f"[search_shipments_by_products DEBUG] Creati {len(shipment_batches_for_celery)} batch Celery.")

        for i, batch_of_shipments in enumerate(shipment_batches_for_celery):
            batch_ids = [s.id for s in batch_of_shipments] # Assumendo che gli oggetti shipment abbiano 'id'
            logger.debug(f"[search_shipments_by_products DEBUG] Invio batch Celery {i+1} con IDs: {batch_ids}")
            # Determina il tipo di spedizione (se misto, potresti doverlo passare o inferire)
            # Per ora assumiamo 'outbound' come da logica precedente, ma potrebbe servire più flessibilità
            # Se hai shipment_type dalla form, usalo:
            shipment_type_for_task = request.POST.get('shipment_type', 'outbound') # o default
            
            process_shipment_batch.apply_async(
                args=[search_id, batch_ids, merchant_id, i + 1, shipment_type_for_task], # Aggiunto shipment_type
                countdown=i * 5 # Riduci countdown per test più rapidi, poi aumenta se necessario
            )
        
        logger.info(f"[search_shipments_by_products] Task Celery inviati per {len(found_shipments_for_celery_batch)} spedizioni.")
        return JsonResponse({
            'status': 'processing', 
            'search_id': search_id, 
            'total_shipments_for_processing': len(found_shipments_for_celery_batch),
            'message': 'Ricerca e processamento avviati. I risultati saranno disponibili a breve.'
        })

    # Ritorno per GET non gestito esplicitamente sopra (dovrebbe essere coperto dalla logica GET iniziale)
    logger.debug(f"[search_shipments_by_products DEBUG] Richiesta GET non POST, rendering form base o risultati esistenti.")
    return render(request, 'prep_management/search_shipments.html', context)
