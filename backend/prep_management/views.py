from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from .services import PrepBusinessAPI
from .utils.merchants import get_merchants
from .models import ShipmentStatusUpdate, OutgoingMessage, SearchResultItem, IncomingMessage, TelegramNotification, TelegramMessage
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
from rest_framework.permissions import AllowAny
from django.contrib.auth.models import User

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

        # DEDUPLICAZIONE CON LOCK TRANSAZIONALE: Controlla se esiste già un webhook simile negli ultimi 10 minuti
        from django.utils import timezone
        from datetime import timedelta
        from django.db import transaction
        
        ten_minutes_ago = timezone.now() - timedelta(minutes=10)
        
        # Usa select_for_update per evitare race conditions
        with transaction.atomic():
            existing_webhook = ShipmentStatusUpdate.objects.select_for_update().filter(
                shipment_id=webhook_data.get('shipment_id'),
                event_type=webhook_data.get('event_type', 'other'),
                new_status=webhook_data.get('new_status', 'other'),
                merchant_id=merchant_id,
                created_at__gte=ten_minutes_ago
            ).first()
            
            if existing_webhook:
                logger.warning(f"[webhook_dedup] Webhook duplicato ignorato per shipment_id={webhook_data.get('shipment_id')}, event_type={webhook_data.get('event_type')}, existing_id={existing_webhook.id}")
                return existing_webhook
        
        # Crea il record di aggiornamento (fuori dal transaction atomico)
        try:
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
            logger.info(f"[webhook_saved] Nuovo webhook salvato ID: {shipment_update.id} per shipment_id={webhook_data.get('shipment_id')}, event_type={webhook_data.get('event_type')}")
            
        except Exception as e:
            from django.db import IntegrityError
            if isinstance(e, IntegrityError) and 'unique_webhook_per_shipment_event' in str(e):
                # Webhook duplicato bloccato dal constraint database
                logger.warning(f"[webhook_dedup_constraint] Webhook duplicato bloccato da constraint DB per shipment_id={webhook_data.get('shipment_id')}, event_type={webhook_data.get('event_type')}")
                # Trova il webhook esistente
                existing_webhook = ShipmentStatusUpdate.objects.filter(
                    shipment_id=webhook_data.get('shipment_id'),
                    event_type=webhook_data.get('event_type', 'other'),
                    new_status=webhook_data.get('new_status', 'other'),
                    merchant_id=merchant_id
                ).first()
                return existing_webhook
            else:
                # Altro errore, rilancia
                logger.error(f"[webhook_save_error] Errore nel salvare webhook: {str(e)}")
                raise
        
        # Elabora subito l'evento appena salvato (come era prima)
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

@csrf_exempt
def telegram_webhook(request):
    """
    Webhook per ricevere aggiornamenti dal bot Telegram.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method allowed'}, status=405)
    
    try:
        # Parse del payload JSON
        data = json.loads(request.body.decode('utf-8'))
        logger.info(f"Webhook Telegram ricevuto: {data}")
        
        # Controlla se è un messaggio
        if 'message' in data:
            message = data['message']
            chat_id = message['chat']['id']
            text = message.get('text', '')
            user_info = message.get('from', {})
            
            # Estrarre informazioni reply se presente
            reply_to_message = message.get('reply_to_message')
            
            # Gestisci il comando /start
            if text.startswith('/start'):
                handle_start_command(chat_id, user_info)
            
            # Gestisci scelta lingua
            elif text.lower().strip() in ['i', 'e']:
                handle_language_selection(chat_id, text.lower().strip(), user_info)
            
            # Controlla se è una email (registrazione)
            elif '@' in text and '.' in text:
                handle_email_registration(chat_id, text.strip(), user_info)
            
            # Comandi di aiuto
            elif text.lower() in ['/help', 'aiuto', 'help']:
                handle_help_command(chat_id)
            
            # Comando per test
            elif text.lower() in ['/test', 'test']:
                handle_test_command(chat_id)
            
            # Comando per status
            elif text.lower() in ['/status', 'status']:
                handle_status_command(chat_id)
            
            # Comando per cambiare lingua
            elif text.lower() in ['/language', '/lingua', 'language', 'lingua']:
                handle_language_command(chat_id)
            
            else:
                # Gestisci messaggio bidirezionale (conversazione)
                handle_bidirectional_message(chat_id, text, reply_to_message)
        
        return JsonResponse({'ok': True})
        
    except Exception as e:
        logger.error(f"Errore nel webhook Telegram: {str(e)}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


def handle_start_command(chat_id, user_info):
    """Gestisce il comando /start del bot."""
    from .services import telegram_service
    from .translations import get_text
    
    # Invia messaggio bilingue per scelta lingua
    welcome_message = get_text('welcome_bilingual')
    
    try:
        telegram_service.send_message(chat_id, welcome_message)
    except Exception as e:
        logger.error(f"Errore nell'invio messaggio di benvenuto: {str(e)}")


def handle_email_registration(chat_id, email, user_info):
    """Gestisce la registrazione dell'email."""
    try:
        from .services import register_telegram_user, telegram_service
        from .translations import get_text, get_user_language
        
        # Ottieni la lingua dell'utente
        user_lang = get_user_language(chat_id)
        
        # Validazione email di base
        if not email or '@' not in email or '.' not in email:
            error_message = get_text('invalid_email', lang=user_lang)
            telegram_service.send_message(chat_id, error_message)
            return
        
        # Registra l'utente
        success, message, user = register_telegram_user(chat_id, email, user_info)
    except Exception as e:
        logger.error(f"Errore nella registrazione email {email}: {str(e)}")
        from .services import telegram_service
        from .translations import get_text, get_user_language
        
        user_lang = get_user_language(chat_id)
        error_message = get_text('system_error', lang=user_lang)
        telegram_service.send_message(chat_id, error_message)
        return
    
    if success:
        # Aggiorna la lingua se era un utente temporaneo
        if user:
            user.language_code = user_lang
            user.save()
        
        success_message = get_text('registration_success', lang=user_lang, email=email, chat_id=chat_id)
        telegram_service.send_message(chat_id, success_message)
        
        # Invia un messaggio di test
        test_message = get_text('registration_test', lang=user_lang)
        telegram_service.send_message(chat_id, test_message)
        
    else:
        # Gestisci messaggi di errore specifici
        if message == "email_not_found_in_system":
            error_message = get_text('email_not_found_in_system', lang=user_lang, email=email)
        else:
            error_message = get_text('registration_error', lang=user_lang, message=message)
        telegram_service.send_message(chat_id, error_message)


def handle_language_selection(chat_id, language_choice, user_info):
    """Gestisce la selezione della lingua dell'utente."""
    from .services import telegram_service
    from .translations import get_text
    
    try:
        # Mappa scelta lingua al codice
        language_map = {'i': 'it', 'e': 'en'}
        
        if language_choice not in language_map:
            # Scelta non valida
            error_message = get_text('invalid_language_choice')
            telegram_service.send_message(chat_id, error_message)
            return
        
        language_code = language_map[language_choice]
        
        # Imposta la lingua nell'utente se già registrato
        from .models import TelegramNotification
        users = TelegramNotification.objects.filter(chat_id=chat_id)
        if users.exists():
            users.update(language_code=language_code)
        
        # Invia messaggio di conferma e istruzioni per la registrazione
        confirmation_message = get_text('language_selected', lang=language_code)
        telegram_service.send_message(chat_id, confirmation_message)
        
        # Memorizza la lingua per i nuovi utenti (useremo session temporanea)
        # Per ora salviamo nel database anche senza registrazione completa
        if not users.exists():
            # Crea record temporaneo per memorizzare la lingua
            temp_user, created = TelegramNotification.objects.get_or_create(
                chat_id=chat_id,
                defaults={
                    'email': f'temp_{chat_id}@temp.com',  # Email temporanea
                    'language_code': language_code,
                    'is_active': False,  # Non attivo finché non si registra veramente
                    'username': user_info.get('username'),
                    'first_name': user_info.get('first_name'),
                    'last_name': user_info.get('last_name'),
                }
            )
            if not created:
                temp_user.language_code = language_code
                temp_user.save()
        
        logger.info(f"Lingua impostata a {language_code} per chat_id {chat_id}")
        
    except Exception as e:
        logger.error(f"Errore nella selezione lingua per {chat_id}: {str(e)}")
        from .services import telegram_service
        error_message = get_text('system_error')
        telegram_service.send_message(chat_id, error_message)


def handle_language_command(chat_id):
    """Gestisce il comando /language per cambiare lingua."""
    from .services import telegram_service
    from .translations import get_text, get_user_language
    
    try:
        # Ottieni la lingua attuale dell'utente
        current_lang = get_user_language(chat_id)
        
        # Invia messaggio per cambiare lingua
        language_message = get_text('language_command', lang=current_lang)
        telegram_service.send_message(chat_id, language_message)
        
    except Exception as e:
        logger.error(f"Errore nel comando language per {chat_id}: {str(e)}")


def handle_help_command(chat_id):
    """Gestisce il comando di aiuto."""
    from .services import telegram_service
    from .translations import get_text, get_user_language
    
    user_lang = get_user_language(chat_id)
    help_message = get_text('help', lang=user_lang)
    
    try:
        telegram_service.send_message(chat_id, help_message)
    except Exception as e:
        logger.error(f"Errore nell'invio messaggio di aiuto: {str(e)}")


def handle_test_command(chat_id):
    """Gestisce il comando di test."""
    from .services import telegram_service
    from .models import TelegramNotification
    from .translations import get_text, get_user_language
    
    user_lang = get_user_language(chat_id)
    
    try:
        # Controlla se l'utente è registrato
        telegram_user = TelegramNotification.objects.get(chat_id=chat_id, is_active=True)
        
        test_message = get_text('test_success', lang=user_lang,
                               full_name=telegram_user.get_full_name(),
                               email=telegram_user.email,
                               chat_id=chat_id,
                               notifications_sent=telegram_user.total_notifications_sent,
                               registration_date=telegram_user.created_at.strftime('%d/%m/%Y alle %H:%M'))
        
        telegram_service.send_message(chat_id, test_message)
        
        # Incrementa il contatore
        telegram_user.increment_notification_count()
        
    except TelegramNotification.DoesNotExist:
        not_registered_message = get_text('test_not_registered', lang=user_lang)
        telegram_service.send_message(chat_id, not_registered_message)
        
    except Exception as e:
        logger.error(f"Errore nel comando test: {str(e)}")
        error_message = "❌ Errore nel test. Riprova più tardi."
        telegram_service.send_message(chat_id, error_message)


def handle_status_command(chat_id):
    """Gestisce il comando /status - mostra informazioni sulla registrazione."""
    from .services import telegram_service
    from .models import TelegramNotification
    from .translations import get_text, get_user_language
    import pytz
    
    user_lang = get_user_language(chat_id)
    
    try:
        # Controlla se l'utente è registrato
        telegram_user = TelegramNotification.objects.get(chat_id=chat_id, is_active=True)
        
        # Formatta date con timezone italiano
        rome_tz = pytz.timezone('Europe/Rome')
        created_at_local = telegram_user.created_at.astimezone(rome_tz)
        
        if telegram_user.last_notification_at:
            last_notification_local = telegram_user.last_notification_at.astimezone(rome_tz)
            last_notification = get_text('last_notification', lang=user_lang, 
                                       date=last_notification_local.strftime('%d/%m/%Y alle %H:%M'))
        else:
            last_notification = get_text('no_notifications', lang=user_lang)
        
        status_message = get_text('status', lang=user_lang,
                                full_name=telegram_user.get_full_name(),
                                email=telegram_user.email,
                                chat_id=chat_id,
                                registration_date=created_at_local.strftime('%d/%m/%Y alle %H:%M'),
                                notifications_sent=telegram_user.total_notifications_sent,
                                last_notification=last_notification)
        
        telegram_service.send_message(chat_id, status_message)
        
    except TelegramNotification.DoesNotExist:
        not_registered_message = get_text('status_not_registered', lang=user_lang)
        telegram_service.send_message(chat_id, not_registered_message)
        
    except Exception as e:
        logger.error(f"Errore nel comando status: {str(e)}")
        error_message = "❌ Errore nel recupero del tuo status. Riprova più tardi."
        telegram_service.send_message(chat_id, error_message)


def handle_bidirectional_message(chat_id, message_text, reply_to_message=None):
    """Gestisce i messaggi bidirezionali delle conversazioni."""
    from .chat_manager import ChatManager
    from .services import telegram_service
    from .translations import get_text, get_user_language
    
    try:
        chat_manager = ChatManager()
        result = chat_manager.handle_customer_message(chat_id, message_text, reply_to_message)
        
        if not result.get('success'):
            # Se c'è un errore, invia messaggio di errore o comando sconosciuto
            if result.get('error') == 'Utente non registrato':
                send_unknown_command_message(chat_id)
            else:
                user_lang = get_user_language(chat_id)
                error_message = get_text('system_error', lang=user_lang)
                telegram_service.send_message(chat_id, error_message)
                
    except Exception as e:
        logger.error(f"Errore gestione messaggio bidirezionale {chat_id}: {str(e)}")
        user_lang = get_user_language(chat_id)
        error_message = get_text('system_error', lang=user_lang)
        telegram_service.send_message(chat_id, error_message)


def send_unknown_command_message(chat_id):
    """Invia un messaggio per comando non riconosciuto."""
    from .services import telegram_service
    from .translations import get_text, get_user_language
    
    user_lang = get_user_language(chat_id)
    unknown_message = get_text('unknown_command', lang=user_lang)
    
    try:
        telegram_service.send_message(chat_id, unknown_message)
    except Exception as e:
        logger.error(f"Errore nell'invio messaggio comando sconosciuto: {str(e)}")


@api_view(['GET'])
@permission_classes([AllowAny])
def telegram_bot_info(request):
    """
    Endpoint per ottenere informazioni sul bot Telegram.
    """
    from .services import telegram_service
    
    try:
        if not telegram_service.bot_token:
            return Response({
                'error': 'Bot Telegram non configurato',
                'configured': False
            }, status=400)
        
        # Ottieni info del bot
        url = f"{telegram_service.base_url}/getMe"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            bot_info = response.json()
            return Response({
                'configured': True,
                'bot_info': bot_info.get('result', {}),
                'webhook_url': request.build_absolute_uri('/prep_management/telegram/webhook/')
            })
        else:
            return Response({
                'error': 'Errore nel recuperare info bot',
                'configured': False
            }, status=400)
            
    except Exception as e:
        return Response({
            'error': str(e),
            'configured': False
        }, status=500)


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def set_telegram_webhook(request):
    """
    Endpoint per configurare il webhook del bot Telegram.
    Accetta sia GET che POST per facilità d'uso.
    """
    from .services import telegram_service
    
    try:
        if not telegram_service.bot_token:
            return Response({
                'success': False,
                'error': 'Bot Telegram non configurato (TELEGRAM_BOT_TOKEN mancante)',
                'configured': False
            }, status=400)
        
        # Forza HTTPS per il webhook (richiesto da Telegram)
        webhook_url = request.build_absolute_uri('/prep_management/telegram/webhook/')
        if webhook_url.startswith('http://'):
            webhook_url = webhook_url.replace('http://', 'https://', 1)
        
        url = f"{telegram_service.base_url}/setWebhook"
        payload = {'url': webhook_url}
        
        response = requests.post(url, data=payload, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            return Response({
                'success': True,
                'webhook_url': webhook_url,
                'telegram_response': result,
                'message': '✅ Webhook configurato con successo!',
                'next_steps': [
                    '1. Testa il bot cercandolo su Telegram',
                    '2. Invia /start per verificare che risponda',
                    '3. Registra un utente con la sua email del Prep Center'
                ]
            })
        else:
            return Response({
                'success': False,
                'error': 'Errore nella configurazione webhook',
                'response': response.text,
                'webhook_url': webhook_url
            }, status=400)
            
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e),
            'webhook_url': request.build_absolute_uri('/prep_management/telegram/webhook/').replace('http://', 'https://', 1) if request else None
        }, status=500)

def create_admin_user(request):
    """
    Vista per creare rapidamente un utente admin per test.
    """
    from django.contrib.auth.models import User
    
    if request.method == 'POST':
        try:
            username = request.POST.get('username', 'admin')
            password = request.POST.get('password', 'admin123')
            email = request.POST.get('email', 'admin@preprocenter.com')
            
            # Controlla se l'utente esiste già
            if User.objects.filter(username=username).exists():
                return JsonResponse({
                    'success': False,
                    'message': f'Utente {username} esiste già'
                })
            
            # Crea l'utente admin
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password
            )
            user.is_staff = True
            user.is_superuser = True
            user.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Utente admin {username} creato con successo',
                'username': username,
                'password': password
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Errore nella creazione admin: {str(e)}'
            })
    
    # GET request - mostra form
    return JsonResponse({
        'message': 'Invia POST con username, password, email per creare admin',
        'example': {
            'username': 'admin',
            'password': 'admin123',
            'email': 'admin@prepcenter.com'
        }
    })

@api_view(['GET'])
@permission_classes([AllowAny])
def telegram_merchants_debug(request):
    """
    Endpoint di debug per vedere tutte le email dei merchant disponibili nel software del Prep Center.
    Utile per troubleshooting delle registrazioni Telegram.
    """
    try:
        from libs.prepbusiness.client import PrepBusinessClient
        import os
        
        # Ottieni configurazione dalle variabili d'ambiente
        api_url = os.getenv('PREP_BUSINESS_API_URL', 'https://dashboard.fbaprepcenteritaly.com/api')
        api_key = os.getenv('PREP_BUSINESS_API_KEY', '')
        
        if not api_key:
            return Response({
                'success': False,
                'error': 'PREP_BUSINESS_API_KEY non configurata',
                'message': 'Configurazione API Prep Center mancante'
            }, status=500)
        
        # Estrai dominio dall'URL
        company_domain = api_url.split('//')[-1].split('/')[0]
        
        # Crea client PrepBusiness
        client = PrepBusinessClient(
            api_key=api_key,
            company_domain=company_domain
        )
        
        # Ottieni tutti i merchant
        merchants_response = client.get_merchants()
        merchants = merchants_response.data if merchants_response else []
        
        # Estrai info merchant
        merchant_info = []
        for merchant in merchants:
            email = getattr(merchant, 'primaryEmail', None) or getattr(merchant, 'email', None)
            merchant_info.append({
                'id': merchant.id,
                'name': merchant.name,
                'email': email,
                'enabled': getattr(merchant, 'enabled', 'N/A')
            })
        
        return Response({
            'success': True,
            'total_merchants': len(merchants),
            'merchants': merchant_info,
            'emails': [m['email'] for m in merchant_info if m['email']],
            'message': f'Trovati {len(merchants)} merchant nel software del Prep Center'
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e),
            'message': 'Errore nel recupero dei merchant dal software del Prep Center'
        }, status=500)


def telegram_debug(request):
    """
    Vista di debug per controllare lo stato del sistema Telegram.
    """
    try:
        # Eventi recenti
        recent_events = list(ShipmentStatusUpdate.objects.order_by('-created_at')[:10].values(
            'id', 'event_type', 'shipment_id', 'processed', 'created_at', 'merchant_id', 'process_success'
        ))
        
        # Utenti Telegram registrati
        telegram_users = list(TelegramNotification.objects.values(
            'email', 'chat_id', 'is_active', 'created_at', 'total_notifications_sent'
        ))
        
        # Messaggi Telegram recenti
        telegram_messages = list(TelegramMessage.objects.select_related('telegram_user').order_by('-created_at')[:10].values(
            'id', 'telegram_user__email', 'status', 'event_type', 'shipment_id', 'created_at', 'sent_at', 'error_message'
        ))
        
        # Statistiche
        stats = {
            'total_events': ShipmentStatusUpdate.objects.count(),
            'processed_events': ShipmentStatusUpdate.objects.filter(processed=True).count(),
            'failed_events': ShipmentStatusUpdate.objects.filter(processed=True, process_success=False).count(),
            'total_telegram_users': TelegramNotification.objects.count(),
            'active_telegram_users': TelegramNotification.objects.filter(is_active=True).count(),
            'total_telegram_messages': TelegramMessage.objects.count(),
            'sent_messages': TelegramMessage.objects.filter(status='sent').count(),
            'failed_messages': TelegramMessage.objects.filter(status='failed').count(),
        }
        
        # Info configurazione
        config_info = {
            'telegram_bot_token_configured': bool(settings.TELEGRAM_BOT_TOKEN),
            'telegram_webhook_url': getattr(settings, 'TELEGRAM_WEBHOOK_URL', None),
            'prep_business_api_key_configured': bool(getattr(settings, 'PREP_BUSINESS_API_KEY', None) or 
                                                   os.environ.get('PREP_BUSINESS_API_KEY')),
        }
        
        return JsonResponse({
            'success': True,
            'stats': stats,
            'config': config_info,
            'recent_events': recent_events,
            'telegram_users': telegram_users,
            'telegram_messages': telegram_messages,
            'debug_notes': [
                'Controlla che ci siano eventi recenti',
                'Verifica che gli utenti Telegram siano registrati',
                'Controlla se i messaggi vengono inviati o falliscono',
                'Eventi processati ma non inviati indicano un problema nel codice di notifica'
            ]
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'message': 'Errore nel recupero dati debug'
        })

@api_view(['GET'])
@permission_classes([AllowAny])
def telegram_admin_debug(request):
    """
    Endpoint di debug per verificare multiple admin e nomi clienti.
    """
    try:
        from .models import TelegramNotification
        from .services import get_merchant_name_by_email, ADMIN_EMAIL
        
        debug_info = {
            'admin_email': ADMIN_EMAIL,
            'admin_users': [],
            'customer_tests': [],
            'stats': {}
        }
        
        # 1. Verifica admin registrati
        admin_users = TelegramNotification.objects.filter(
            email=ADMIN_EMAIL,
            is_active=True
        )
        
        for admin in admin_users:
            debug_info['admin_users'].append({
                'chat_id': admin.chat_id,
                'username': admin.username,
                'first_name': admin.first_name,
                'language_code': admin.language_code,
                'created_at': admin.created_at.isoformat() if admin.created_at else None,
                'is_valid_chat_id': admin.chat_id != 999999998
            })
        
        # 2. Test recupero nomi clienti
        test_emails = [
            'prep@easyavant.com',
            'glomatservice@gmail.com',
            'alyxsrl@gmail.com',
            'demo@wifiexpress.it'
        ]
        
        for email in test_emails:
            customer_name = get_merchant_name_by_email(email)
            debug_info['customer_tests'].append({
                'email': email,
                'name': customer_name,
                'display': customer_name or email
            })
        
        # 3. Statistiche generali
        all_users = TelegramNotification.objects.filter(is_active=True)
        debug_info['stats'] = {
            'total_active_users': all_users.count(),
            'admin_users_count': admin_users.count(),
            'customer_users_count': all_users.exclude(email=ADMIN_EMAIL).count(),
            'invalid_chat_ids': all_users.filter(chat_id=999999998).count()
        }
        
        # 4. Test simulazione notifica
        if admin_users.exists():
            debug_info['simulation'] = {
                'would_send_to_admin_count': admin_users.count(),
                'admin_chat_ids': [u.chat_id for u in admin_users if u.chat_id != 999999998]
            }
        else:
            debug_info['simulation'] = {
                'would_send_to_admin_count': 0,
                'warning': 'Nessun admin registrato con email ' + ADMIN_EMAIL
            }
        
        return Response({
            'success': True,
            'debug_info': debug_info
        })
        
    except Exception as e:
        import traceback
        return Response({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }, status=500)

@api_view(['POST'])
@permission_classes([AllowAny])
def test_multiple_admin_notification(request):
    """
    Endpoint di test per simulare l'invio di notifiche a multiple admin.
    """
    try:
        from .services import send_telegram_notification, ADMIN_EMAIL
        
        # Email di test (deve essere un cliente valido)
        test_email = request.data.get('email', 'prep@easyavant.com')
        test_message = request.data.get('message', '🧪 Test notifica multiple admin')
        
        # Log prima dell'invio
        logger.info(f"[TEST] Invio notifica test da {test_email} con messaggio: {test_message}")
        
        # Invia notifica di test
        success = send_telegram_notification(
            email=test_email,
            message=test_message,
            event_type='test'
        )
        
        # Verifica quanti admin avrebbero dovuto ricevere
        from .models import TelegramNotification
        admin_users = TelegramNotification.objects.filter(
            email=ADMIN_EMAIL,
            is_active=True
        )
        
        valid_admin_users = admin_users.exclude(chat_id=999999998)
        
        result = {
            'success': success,
            'test_email': test_email,
            'test_message': test_message,
            'admin_email': ADMIN_EMAIL,
            'admin_users_total': admin_users.count(),
            'admin_users_valid': valid_admin_users.count(),
            'admin_users_invalid': admin_users.filter(chat_id=999999998).count(),
            'admin_users_details': [
                {
                    'chat_id': u.chat_id,
                    'username': u.username,
                    'first_name': u.first_name,
                    'is_valid': u.chat_id != 999999998
                }
                for u in admin_users
            ]
        }
        
        return Response(result)
        
    except Exception as e:
        import traceback
        return Response({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }, status=500)

@api_view(['GET'])
@permission_classes([AllowAny])
def telegram_users_debug(request):
    """
    Endpoint di debug per vedere tutti gli utenti registrati e le loro email.
    """
    try:
        from .models import TelegramNotification
        from .services import ADMIN_EMAIL
        
        users = TelegramNotification.objects.filter(is_active=True).order_by('email', 'created_at')
        
        users_info = []
        admin_count = 0
        customer_count = 0
        
        for user in users:
            is_admin = user.email == ADMIN_EMAIL
            if is_admin:
                admin_count += 1
            else:
                customer_count += 1
            
            users_info.append({
                'email': user.email,
                'chat_id': user.chat_id,
                'username': user.username,
                'first_name': user.first_name,
                'language_code': user.language_code,
                'is_admin': is_admin,
                'is_valid_chat_id': user.chat_id != 999999998,
                'created_at': user.created_at.isoformat() if user.created_at else None
            })
        
        return Response({
            'success': True,
            'admin_email': ADMIN_EMAIL,
            'total_users': len(users_info),
            'admin_count': admin_count,
            'customer_count': customer_count,
            'users': users_info
        })
        
    except Exception as e:
        import traceback
        return Response({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }, status=500)

@api_view(['POST'])
@permission_classes([AllowAny])
def test_email_normalization(request):
    """
    Endpoint di test per verificare la normalizzazione delle email.
    """
    try:
        from .services import verify_email_in_prepbusiness, get_merchant_name_by_email
        
        test_email = request.data.get('email', 'Info@fbaprepcenteritaly.com')
        
        # Test normalizzazione
        result = {
            'original_email': test_email,
            'normalized_email': test_email.lower().strip() if test_email else None,
            'verify_result': verify_email_in_prepbusiness(test_email),
            'merchant_name': get_merchant_name_by_email(test_email),
            'tests': []
        }
        
        # Test varie email con case diverse
        test_cases = [
            'Info@fbaprepcenteritaly.com',
            'INFO@FBAPREPCENTERITALY.COM',
            'info@fbaprepcenteritaly.com',
            'Prep@easyavant.com',
            'PREP@EASYAVANT.COM',
            'prep@easyavant.com'
        ]
        
        for test_case in test_cases:
            result['tests'].append({
                'email': test_case,
                'normalized': test_case.lower().strip(),
                'valid': verify_email_in_prepbusiness(test_case),
                'merchant_name': get_merchant_name_by_email(test_case)
            })
        
        return Response({
            'success': True,
            'result': result
        })
        
    except Exception as e:
        import traceback
        return Response({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }, status=500)


@api_view(['POST'])
@permission_classes([AllowAny])
def test_inbound_received_notification(request):
    """
    Test per spedizione in entrata ricevuta con conteggi prodotti - numeri uguali (verde)
    """
    try:
        from .services import send_telegram_notification
        
        # Dati di test per inbound_shipment.received
        shipment_data = {
            'shipment_id': 'INBOUND-12345',
            'shipment_name': 'Test Spedizione Entrata - Match',
            'expected_count': 85,
            'received_count': 85,  # Stesso numero = verde
            'merchant_name': 'Test Merchant',
            'new_status': 'received'
        }
        
        success = send_telegram_notification(
            email="info@fbaprepcenteritaly.com",
            message=None,  # Formattazione automatica
            event_type="inbound_shipment.received",
            shipment_id=shipment_data['shipment_id'],
            shipment_data=shipment_data
        )
        
        return Response({
            'success': success,
            'message': f'Test inbound received (stesso numero - verde) - Success: {success}',
            'data': shipment_data
        })
        
    except Exception as e:
        import traceback
        return Response({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }, status=500)


@api_view(['POST'])
@permission_classes([AllowAny])
def test_inbound_received_more(request):  
    """
    Test per spedizione in entrata ricevuta con PIÙ prodotti del previsto (blu)
    """
    try:
        from .services import send_telegram_notification
        
        # Dati di test per inbound_shipment.received - arrivato di più
        shipment_data = {
            'shipment_id': 'INBOUND-67890',
            'shipment_name': 'Test Spedizione Entrata - Surplus',
            'expected_count': 85,
            'received_count': 92,  # Più del previsto = blu
            'merchant_name': 'Test Merchant',
            'new_status': 'received'
        }
        
        success = send_telegram_notification(
            email="info@fbaprepcenteritaly.com",
            message=None,  # Formattazione automatica
            event_type="inbound_shipment.received",
            shipment_id=shipment_data['shipment_id'],
            shipment_data=shipment_data
        )
        
        return Response({
            'success': success,
            'message': f'Test inbound received (arrivato di più - blu) - Success: {success}',
            'data': shipment_data
        })
        
    except Exception as e:
        import traceback
        return Response({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }, status=500)


@api_view(['POST'])
@permission_classes([AllowAny])
def test_inbound_received_less(request):
    """
    Test per spedizione in entrata ricevuta con MENO prodotti del previsto (rosso)
    """
    try:
        from .services import send_telegram_notification
        
        # Dati di test per inbound_shipment.received - arrivato di meno
        shipment_data = {
            'shipment_id': 'INBOUND-11111',
            'shipment_name': 'Test Spedizione Entrata - Shortage',
            'expected_count': 85,
            'received_count': 73,  # Meno del previsto = rosso
            'merchant_name': 'Test Merchant',
            'new_status': 'received'
        }
        
        success = send_telegram_notification(
            email="info@fbaprepcenteritaly.com",
            message=None,  # Formattazione automatica
            event_type="inbound_shipment.received",
            shipment_id=shipment_data['shipment_id'],
            shipment_data=shipment_data
        )
        
        return Response({
            'success': success,
            'message': f'Test inbound received (arrivato di meno - rosso) - Success: {success}',
            'data': shipment_data
        })
        
    except Exception as e:
        import traceback
        return Response({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }, status=500)


@api_view(['GET'])
@permission_classes([])
def test_outbound_closed_with_products(request):
    """
    Endpoint di test per simulare un webhook outbound_shipment.closed con conteggio prodotti.
    """
    try:
        # Simula un payload di webhook per outbound_shipment.closed
        test_payload = {
            "type": "outbound_shipment.closed",
            "data": {
                "id": 99999,
                "name": "Test Outbound Shipment #99999",
                "status": "closed",
                "team_id": 123,
                "created_at": "2024-01-15T10:00:00Z",
                "updated_at": "2024-01-15T14:30:00Z",
                "notes": "Test shipment for products count feature"
            }
        }
        
        logger.info(f"[test_outbound_closed_with_products] 🧪 Simulazione webhook: {test_payload}")
        
        # Elabora il payload usando il processor
        webhook_data = WebhookProcessor.parse_payload(test_payload)
        logger.info(f"[test_outbound_closed_with_products] 📦 Dati processati: {webhook_data}")
        
        # Crea il record di aggiornamento (senza salvare nel DB per il test)
        update_data = {
            'shipment_id': webhook_data.get('shipment_id'),
            'event_type': webhook_data.get('event_type', 'other'),
            'entity_type': webhook_data.get('entity_type', ''),
            'new_status': webhook_data.get('new_status', 'other'),
            'merchant_id': webhook_data.get('merchant_id'),
            'payload': webhook_data.get('payload', {})
        }
        
        logger.info(f"[test_outbound_closed_with_products] 📋 Dati update: {update_data}")
        
        # Test formattazione messaggio con conteggio prodotti
        shipment_data = {
            'shipment_id': webhook_data.get('shipment_id'),
            'shipment_name': test_payload['data']['name'],
            'products_count': 65,  # Simula 65 prodotti
            'notes': test_payload['data'].get('notes', '')
        }
        
        # Formatta messaggio di test
        test_message = format_shipment_notification(
            "outbound_shipment.closed", 
            shipment_data,
            "test@example.com"
        )
        
        logger.info(f"[test_outbound_closed_with_products] 💬 Messaggio formattato: {test_message}")
        
        return JsonResponse({
            'success': True,
            'message': 'Test webhook outbound_shipment.closed eseguito',
            'webhook_data': webhook_data,
            'update_data': update_data,
            'formatted_message': test_message,
            'test_payload': test_payload
        })
        
    except Exception as e:
        logger.error(f"[test_outbound_closed_with_products] ❌ Errore durante test: {str(e)}")
        logger.exception("Traceback completo:")
        return JsonResponse({
            'success': False,
            'error': str(e),
            'message': 'Errore durante test webhook'
        }, status=500)

@api_view(['POST'])
@permission_classes([])
def test_residual_inbound_creation(request):
    """
    Endpoint di test per simulare la creazione di un inbound residual.
    Accetta parametri per testare diversi scenari.
    """
    try:
        # Parametri di test dal request
        outbound_shipment_id = request.data.get('outbound_shipment_id', '99999')
        merchant_id = request.data.get('merchant_id', '123')
        test_scenario = request.data.get('scenario', 'default')
        
        logger.info(f"[test_residual_inbound_creation] 🧪 Test residual creation - Scenario: {test_scenario}")
        
        # Crea un mock update object per testare il processor
        mock_update = type('MockUpdate', (), {
            'shipment_id': outbound_shipment_id,
            'merchant_id': merchant_id,
            'event_type': 'outbound_shipment.closed',
            'payload': {
                'type': 'outbound_shipment.closed',
                'data': {
                    'id': int(outbound_shipment_id),
                    'name': f'Test Outbound {test_scenario}',
                    'status': 'closed'
                }
            }
        })()
        
        # Inizializza il processor
        from .event_handlers import WebhookEventProcessor
        processor = WebhookEventProcessor()
        
        if not processor.client:
            return JsonResponse({
                'success': False,
                'error': 'PrepBusiness client non disponibile per test',
                'message': 'Client API non inizializzato'
            }, status=500)
        
        logger.info(f"[test_residual_inbound_creation] 🚀 Inizio elaborazione mock update")
        
        # Esegui il test del processore
        result = processor._process_outbound_shipment_closed(mock_update)
        
        logger.info(f"[test_residual_inbound_creation] 📋 Risultato elaborazione: {result}")
        
        return JsonResponse({
            'success': True,
            'message': 'Test residual inbound creation completato',
            'test_scenario': test_scenario,
            'outbound_shipment_id': outbound_shipment_id,
            'merchant_id': merchant_id,
            'processing_result': result
        })
        
    except Exception as e:
        logger.error(f"[test_residual_inbound_creation] ❌ Errore durante test: {str(e)}")
        logger.exception("Traceback completo:")
        return JsonResponse({
            'success': False,
            'error': str(e),
            'message': 'Errore durante test residual creation'
        }, status=500)

@api_view(['GET'])
@permission_classes([])
def test_residual_logic_simple(request):
    """
    Endpoint GET semplice per testare la logica residual senza parametri.
    """
    try:
        logger.info("[test_residual_logic_simple] 🧪 Test semplice logica residual")
        
        # Test della logica di calcolo con dati mock
        inbound_items = [
            {'item_id': 1, 'title': 'Prodotto Test 1', 'expected_quantity': 10, 'actual_quantity': 10},
            {'item_id': 2, 'title': 'Prodotto Test 2', 'expected_quantity': 5, 'actual_quantity': 4},
        ]
        
        outbound_items = [
            {'item_id': 1, 'quantity': 7},
            {'item_id': 2, 'quantity': 3},
        ]
        
        # Importa il processor per testare la logica
        from .event_handlers import WebhookEventProcessor
        processor = WebhookEventProcessor()
        
        # Test del calcolo residual
        residual_items = processor._calculate_residual_items(inbound_items, outbound_items)
        
        # Test della generazione nome
        test_name = processor._generate_residual_name("Test Shipment", "123")
        
        return JsonResponse({
            'success': True,
            'message': 'Test logica residual completato',
            'test_data': {
                'inbound_items': inbound_items,
                'outbound_items': outbound_items,
                'residual_items': residual_items,
                'generated_name': test_name
            },
            'client_available': processor.client is not None
        })
        
    except Exception as e:
        logger.error(f"[test_residual_logic_simple] ❌ Errore: {str(e)}")
        logger.exception("Traceback:")
        return JsonResponse({
            'success': False,
            'error': str(e),
            'message': 'Errore durante test logica residual'
        }, status=500)

# Debug function removed to fix crash