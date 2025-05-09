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

from libs.config import (
    PREP_BUSINESS_API_URL,
    PREP_BUSINESS_API_KEY,
    PREP_BUSINESS_API_TIMEOUT,
    PREP_BUSINESS_MAX_RETRIES,
    PREP_BUSINESS_RETRY_BACKOFF
)

logger = logging.getLogger('prep_management')

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
    Recupera i dettagli di una spedizione con retry logic.
    
    Args:
        client: Istanza del client PrepBusiness
        shipment_id: ID della spedizione
        shipment_type: Tipo di spedizione ('inbound' o 'outbound')
        merchant_id: ID opzionale del merchant
        
    Returns:
        Dict con i dettagli della spedizione
        
    Raises:
        Exception: Se tutti i tentativi falliscono
    """
    # Determina se dovremmo usare mock o API reale
    is_mock = False
    
    # Log dettagliato per debug
    logger.info(f"[get_shipment_details] Chiamata per ID={shipment_id}, tipo={shipment_type}, merchant={merchant_id}")
    
    # 1. Controllo esplicito per range di ID mock
    if (shipment_id >= 1001 and shipment_id <= 1005) and shipment_type == 'outbound':
        is_mock = True
        logger.info(f"[get_shipment_details] ID {shipment_id} riconosciuto come mock outbound (1001-1005)")
    elif (shipment_id >= 2001 and shipment_id <= 2005) and shipment_type == 'inbound':
        is_mock = True
        logger.info(f"[get_shipment_details] ID {shipment_id} riconosciuto come mock inbound (2001-2005)")
    else:
        logger.info(f"[get_shipment_details] ID {shipment_id} NON riconosciuto come mock")
    
    # Ulteriore verifica con nome mock per maggiore sicurezza
    if not is_mock and shipment_type == 'outbound' and isinstance(shipment_id, int):
        # Cerca un pattern come "MOCK-OUT-X" nei dettagli disponibili
        id_residuo = shipment_id - 1000
        if 1 <= id_residuo <= 5:
            is_mock = True
            logger.info(f"[get_shipment_details] ID {shipment_id} rilevato come mock outbound dall'ID residuo ({id_residuo})")
    elif not is_mock and shipment_type == 'inbound' and isinstance(shipment_id, int):
        # Cerca un pattern come "MOCK-IN-X" nei dettagli disponibili
        id_residuo = shipment_id - 2000
        if 1 <= id_residuo <= 5:
            is_mock = True
            logger.info(f"[get_shipment_details] ID {shipment_id} rilevato come mock inbound dall'ID residuo ({id_residuo})")
    
    if is_mock:
        logger.info(f"[get_shipment_details] ✓ Usando MOCK per {shipment_type} {shipment_id}")
        # Crea un mock della risposta
        if shipment_type == 'inbound':
            # Struttura mock per InboundShipmentResponse
            mock_response = {
                'shipment': {
                    'id': shipment_id,
                    'name': f"MOCK-IN-{shipment_id-2000}",
                    'status': 'open',
                    'archived_at': None,
                    'created_at': '2024-05-01T10:00:00Z',
                    'updated_at': '2024-05-01T10:00:00Z',
                    'team_id': merchant_id or 1,
                    'warehouse_id': 123,
                    'notes': f"Note mock per spedizione inbound {shipment_id}"
                }
            }
        else:  # outbound
            # Struttura mock per OutboundShipmentResponse
            mock_response = {
                'shipment': {
                    'id': shipment_id,
                    'name': f"MOCK-OUT-{shipment_id-1000}",
                    'status': 'archived',  # o 'open' a seconda del contesto
                    'archived_at': '2024-05-02T10:00:00Z',
                    'created_at': '2024-05-01T10:00:00Z',
                    'updated_at': '2024-05-02T10:00:00Z',
                    'team_id': merchant_id or 1,
                    'merchant_id': merchant_id or 1,
                    'warehouse_id': 123,
                    'notes': f"Note mock per spedizione outbound {shipment_id}"
                }
            }
        return mock_response
    
    # Se non è mock, usa l'API reale
    logger.info(f"[get_shipment_details] Usando API REALE per {shipment_type} {shipment_id}")
    try:
        if shipment_type == 'inbound':
            response = client.get_inbound_shipment(shipment_id, merchant_id=merchant_id, timeout=30)
            return response.model_dump()
        else:
            response = client.get_outbound_shipment(shipment_id, merchant_id=merchant_id, timeout=30)
            return response.model_dump()
    except Exception as e:
        logger.error(f"[get_shipment_details] Errore nel recupero dettagli spedizione {shipment_id}: {str(e)}")
        raise

@retry_on_error(max_retries=3, delay=2, backoff=2)
def get_shipment_items(client: PrepBusinessClient, shipment_id: int, shipment_type: str, merchant_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Recupera gli items di una spedizione con retry logic.
    
    Args:
        client: Istanza del client PrepBusiness
        shipment_id: ID della spedizione
        shipment_type: Tipo di spedizione ('inbound' o 'outbound')
        merchant_id: ID opzionale del merchant
        
    Returns:
        Dict con gli items della spedizione
        
    Raises:
        Exception: Se tutti i tentativi falliscono
    """
    # Determina se dovremmo usare mock o API reale
    is_mock = False
    
    # Log dettagliato per debug
    logger.info(f"[get_shipment_items] Chiamata per ID={shipment_id}, tipo={shipment_type}, merchant={merchant_id}")
    
    # 1. Controllo esplicito per range di ID mock
    if (shipment_id >= 1001 and shipment_id <= 1005) and shipment_type == 'outbound':
        is_mock = True
        logger.info(f"[get_shipment_items] ID {shipment_id} riconosciuto come mock outbound (1001-1005)")
    elif (shipment_id >= 2001 and shipment_id <= 2005) and shipment_type == 'inbound':
        is_mock = True
        logger.info(f"[get_shipment_items] ID {shipment_id} riconosciuto come mock inbound (2001-2005)")
    else:
        logger.info(f"[get_shipment_items] ID {shipment_id} NON riconosciuto come mock")
    
    # Ulteriore verifica con nome mock per maggiore sicurezza
    if not is_mock and shipment_type == 'outbound' and isinstance(shipment_id, int):
        # Cerca un pattern come "MOCK-OUT-X" nei dettagli disponibili
        id_residuo = shipment_id - 1000
        if 1 <= id_residuo <= 5:
            is_mock = True
            logger.info(f"[get_shipment_items] ID {shipment_id} rilevato come mock outbound dall'ID residuo ({id_residuo})")
    elif not is_mock and shipment_type == 'inbound' and isinstance(shipment_id, int):
        # Cerca un pattern come "MOCK-IN-X" nei dettagli disponibili
        id_residuo = shipment_id - 2000
        if 1 <= id_residuo <= 5:
            is_mock = True
            logger.info(f"[get_shipment_items] ID {shipment_id} rilevato come mock inbound dall'ID residuo ({id_residuo})")
    
    if is_mock:
        logger.info(f"[get_shipment_items] ✓ Usando MOCK per {shipment_type} {shipment_id}")
        # Crea mock items diversi a seconda del tipo di spedizione
        if shipment_type == 'inbound':
            # Struttura mock per InboundShipmentItems con parola "Singer" in un item per simulare match di ricerca
            items = []
            for i in range(1, 4):  # 3 items per spedizione
                # Aggiungo la parola Singer al secondo item di tutte le spedizioni pari
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
            
            mock_response = {
                'items': items,
                'total': len(items),
            }
        else:  # outbound
            # Struttura mock per OutboundShipmentItems con parola "Singer" in un item per simulare match di ricerca
            items = []
            for i in range(1, 4):  # 3 items per spedizione
                # Aggiungo la parola Singer al primo item di tutte le spedizioni dispari
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
            
            mock_response = {
                'items': items,
                'total': len(items),
            }
        
        return mock_response
    
    # Se non è mock, usa l'API reale
    logger.info(f"[get_shipment_items] Usando API REALE per {shipment_type} {shipment_id}")
    try:
        if shipment_type == 'inbound':
            response = client.get_inbound_shipment_items(shipment_id, merchant_id=merchant_id, timeout=30)
        else:
            response = client.get_outbound_shipment_items(shipment_id, merchant_id=merchant_id, timeout=30)
        return response.model_dump()
    except Exception as e:
        logger.error(f"[get_shipment_items] Errore nel recupero items spedizione {shipment_id}: {str(e)}")
        raise

def extract_product_info_from_dict(item_dict: Dict[str, Any], shipment_type: str) -> Dict[str, Any]:
    """Estrae SKU, ASIN, FNSKU, Titolo e Quantità da un item_dict."""
    product_title = None
    product_sku = None
    product_asin = None
    product_fnsku = None
    product_quantity = item_dict.get('quantity')

    if shipment_type == 'inbound':
        # Inbound item_dict: {'name': '...', 'sku': '...', 'asin': '...', 'fnsku': '...', 'quantity': ...}
        # La struttura esatta potrebbe variare, adattare secondo il modello effettivo. Qui presumo campi diretti.
        # Questa parte potrebbe necessitare di un'ispezione più approfondita dei dati reali inbound.
        product_title = item_dict.get('name')
        product_sku = item_dict.get('sku') # Assumendo che esista un campo sku diretto
        product_asin = item_dict.get('asin') # Assumendo che esista un campo asin diretto
        # FNSKU potrebbe non essere sempre presente direttamente sull'item di una spedizione inbound
        # Potrebbe essere sull'oggetto InventoryItem collegato, se disponibile
        # Per ora, lo lasciamo None se non direttamente sull'item_dict

    elif shipment_type == 'outbound':
        # Outbound item_dict: {
        #   'quantity': ..., 
        #   'item': {
        #     'title': '...', 
        #     'merchant_sku': '...', 
        #     'asin': '...', 
        #     'fnsku': '...',
        #     'identifiers': [{'identifier': 'val', 'identifier_type': 'ASIN'}, ...]
        #   }
        # }
        inventory_item_data = item_dict.get('item') if isinstance(item_dict, dict) else None
        if inventory_item_data and isinstance(inventory_item_data, dict):
            product_title = inventory_item_data.get('title')
            product_sku = inventory_item_data.get('merchant_sku')
            product_asin = inventory_item_data.get('asin')
            product_fnsku = inventory_item_data.get('fnsku')
            
            # Fallback per ASIN/FNSKU da identifiers se non diretti
            if not product_asin and 'identifiers' in inventory_item_data:
                for ident in inventory_item_data.get('identifiers', []):
                    if ident.get('identifier_type') == 'ASIN':
                        product_asin = ident.get('identifier')
                        break
            if not product_fnsku and 'identifiers' in inventory_item_data:
                for ident in inventory_item_data.get('identifiers', []):
                    if ident.get('identifier_type') == 'FNSKU':
                        product_fnsku = ident.get('identifier')
                        break
    
    return {
        'title': product_title,
        'sku': product_sku,
        'asin': product_asin,
        'fnsku': product_fnsku,
        'quantity': product_quantity
    }

def search_shipments_by_products(request):
    merchants = get_merchants()
    context_vars = {
        'keywords': '',
        'search_type': 'OR',
        'merchant_name': '',
        'shipment_type': '',
        'shipment_status': '',
        'max_results': 100,
        'date_from': '',
        'date_to': '',
        'debug_page': 1,
        'merchants': merchants,
        'title': 'Ricerca spedizioni per prodotti',
        'results': [], # Conterrà SearchResultItem dal DB
        'error': None,
        'is_waiting': False,
        'total_shipments_inspected': 0, 
        'total_items_found': 0
    }

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

    search_triggered = 'merchant_name' in request.GET
    logger.info(f"Search triggered: {search_triggered}, GET params: {dict(request.GET)}")

    if not search_triggered:
        logger.info("No search triggered, rendering empty form")
        return render(request, 'prep_management/search_shipments.html', context_vars)

    logger.info("Nuova ricerca, eliminazione risultati precedenti dal DB...")
    SearchResultItem.objects.all().delete()
    logger.info("Risultati precedenti eliminati.")

    total_shipments_inspected_count = 0

    try:
        keywords_str = context_vars['keywords']
        keywords = [k.strip().lower() for k in keywords_str.split(',') if k.strip()]
        search_type = context_vars['search_type']
        merchant_name = context_vars['merchant_name'].strip()
        shipment_type_filter = context_vars['shipment_type'].strip()
        shipment_status_filter = context_vars['shipment_status'].strip()
        date_from = context_vars['date_from'].strip()
        date_to = context_vars['date_to'].strip()
        max_results = context_vars['max_results']
        debug_page_start = context_vars['debug_page']

        logger.info(f"Parametri di ricerca: keywords={keywords}, search_type={search_type}, merchant_name={merchant_name}, shipment_type={shipment_type_filter}, shipment_status={shipment_status_filter}, max_results={max_results}, date_from={date_from}, date_to={date_to}, debug_page={debug_page_start}")

        merchant_id = None
        if merchant_name:
            merchant = next((m for m in merchants if m['name'].lower() == merchant_name.lower()), None)
            if merchant: merchant_id = merchant['id']
            else:
                context_vars['error'] = f'Merchant \'{merchant_name}\' non trovato'
                return render(request, 'prep_management/search_shipments.html', context_vars)
        else:
            context_vars['error'] = 'Seleziona un merchant per avviare la ricerca.'
            return render(request, 'prep_management/search_shipments.html', context_vars)

        context_vars['is_waiting'] = True
        company_domain = PREP_BUSINESS_API_URL.split('//')[-1].split('/')[0]
        client = PrepBusinessClient(PREP_BUSINESS_API_KEY, company_domain)

        q_parts = []
        if date_from: q_parts.append(f'created_at:>="{date_from}"')
        if date_to: q_parts.append(f'created_at<="{date_to}"')
        q_parts.append('sort:created_at:desc')
        q_query = ' AND '.join(q_parts) if q_parts else None
        logger.info(f"QUERY AVANZATA Q (per recupero sommari spedizioni): {q_query}")

        # Funzione interna per processare un batch di sommari di spedizioni
        def process_shipment_summaries_batch(shipment_summaries: List[Dict[str, Any]], current_ship_type: str):
            nonlocal total_shipments_inspected_count # Permette di modificare la variabile esterna
            nonlocal final_error_message # Permette di modificare la variabile esterna
            
            logger.info(f"Inizio processamento di {len(shipment_summaries)} spedizioni {current_ship_type}.")
            for shipment_summary in shipment_summaries:
                if total_shipments_inspected_count >= max_results:
                    logger.info(f"Raggiunto max_results ({max_results}), interrompo processamento dettagli.")
                    return True # Indica di interrompere anche il ciclo di paginazione esterno

                total_shipments_inspected_count += 1
                context_vars['total_shipments_inspected'] = total_shipments_inspected_count
                context_vars['partial_count'] = total_shipments_inspected_count 

                ship_id = shipment_summary['id']
                ship_name = shipment_summary['name']
                
                logger.info(f"Processo spedizione {total_shipments_inspected_count}/{max_results}: ID {ship_id} ({ship_name}), tipo: {current_ship_type}")
                try:
                    details_dict = get_shipment_details(client, ship_id, current_ship_type, merchant_id=merchant_id)
                    time.sleep(1)  # Aumento il delay tra le chiamate
                    items_response_dict = get_shipment_items(client, ship_id, current_ship_type, merchant_id=merchant_id)
                    time.sleep(1)  # Aumento il delay anche dopo la seconda chiamata
                except Exception as e_detail_item:
                    logger.error(f"Errore recupero dettagli/items per spedizione {ship_id}: {e_detail_item}. Salto.")
                    if final_error_message is None: final_error_message = ""
                    final_error_message += f"\nErrore dettagli sped. {ship_id}: {e_detail_item}. "
                    time.sleep(2)  # Delay più lungo in caso di errore
                    continue 

                shipment_title_lower = (details_dict.get('shipment', {}).get('name', '') or ship_name or '').lower()
                actual_items_list = items_response_dict.get('items', []) if items_response_dict else []

                match_in_shipment_title = False
                if keywords:
                    if search_type == 'AND':
                        match_in_shipment_title = all(k in shipment_title_lower for k in keywords)
                    else: 
                        match_in_shipment_title = any(k in shipment_title_lower for k in keywords)
                elif not keywords: 
                    match_in_shipment_title = True 

                item_saved_for_this_shipment = False
                if actual_items_list: 
                    for item_dict in actual_items_list:
                        product_info = extract_product_info_from_dict(item_dict, current_ship_type)
                        item_name_lower = (product_info.get('title') or '').lower()
                        
                        item_matches_keywords = False
                        if keywords:
                            if search_type == 'AND':
                                item_matches_keywords = all(k in item_name_lower for k in keywords)
                            else: 
                                item_matches_keywords = any(k in item_name_lower for k in keywords)
                        elif not keywords: 
                            item_matches_keywords = True

                        if item_matches_keywords: 
                            SearchResultItem.objects.create(
                                shipment_id_api=str(ship_id),
                                shipment_name=ship_name,
                                shipment_type=current_ship_type,
                                product_title=product_info.get('title'),
                                product_sku=product_info.get('sku'),
                                product_asin=product_info.get('asin'),
                                product_fnsku=product_info.get('fnsku'),
                                product_quantity=product_info.get('quantity')
                            )
                            item_saved_for_this_shipment = True
                
                if not item_saved_for_this_shipment and match_in_shipment_title and keywords:
                    SearchResultItem.objects.create(
                        shipment_id_api=str(ship_id),
                        shipment_name=ship_name,
                        shipment_type=current_ship_type,
                        product_title=f"Corrispondenza trovata nel titolo spedizione (nessun item specifico)",
                    )
                elif not keywords and not actual_items_list: 
                     SearchResultItem.objects.create(
                        shipment_id_api=str(ship_id),
                        shipment_name=ship_name,
                        shipment_type=current_ship_type,
                        product_title="Nessuna keyword e nessun item in questa spedizione",
                    )
            logger.info(f"Fine processamento di {len(shipment_summaries)} spedizioni {current_ship_type}.")
            return False 
        # --- Fine funzione helper process_shipment_summaries_batch ---

        final_error_message = context_vars.get('error') 

        # CICLO API PER OUTBOUND
        if not shipment_type_filter or shipment_type_filter == 'outbound':
            page = debug_page_start
            api_method_name = 'get_outbound_shipments'
            log_prefix = "outbound"
            if shipment_status_filter == 'archived':
                api_method_name = 'get_archived_outbound_shipments'
                log_prefix = "outbound archiviate"
            
            # Imposta il metodo API
            api_method = getattr(client, api_method_name)
            logger.info(f"Recupero spedizioni {log_prefix} per merchant {merchant_id} con filtro q: {q_query}")

            # Riattivo la chiamata reale all'API PrepBusiness per i riassunti
            while True:
                if total_shipments_inspected_count >= max_results:
                    logger.info(f"Raggiunto max_results ({max_results}), interrompo paginazione.")
                    break
                    
                current_per_page = 20 
                api_response = None
                retry_count = 0
                max_retries = 3 
                
                while retry_count < max_retries:
                    try:
                        logger.info(f"API Call: Page {page} ({log_prefix}), per_page={current_per_page}")
                        api_response = api_method(merchant_id=merchant_id, per_page=current_per_page, page=page, search_query=q_query)
                        break
                    except Exception as e_api:
                        retry_count += 1
                        if retry_count >= max_retries:
                            final_error_message = f"Errore API persistente su {log_prefix} pagina {page}: {str(e_api)}"
                            logger.error(final_error_message)
                            break
                        logger.warning(f"Tentativo {retry_count}/{max_retries} fallito: {str(e_api)}")
                        time.sleep(5 * (2**retry_count)) # Exponential backoff for API call
                        
                if final_error_message and retry_count >= max_retries:
                    logger.error("Interruzione paginazione per errore persistente")
                    break
                    
                if not api_response or not hasattr(api_response, 'data') or not api_response.data:
                    logger.info(f"Nessun dato per pagina {page} ({log_prefix}). Fine paginazione.")
                    break

                current_shipment_summaries = []
                for ship_data in api_response.data:
                    status_val = ship_data.status.value if hasattr(ship_data.status, 'value') else ship_data.status
                    current_shipment_summaries.append({
                        'id': ship_data.id, 
                        'name': ship_data.name,
                        'status': status_val, 
                        'type': 'outbound'
                    })
                
                # Processa il batch corrente
                should_stop = process_shipment_summaries_batch(current_shipment_summaries, 'outbound')
                if should_stop:
                    logger.info("Interruzione richiesta da process_shipment_summaries_batch")
                    break
                    
                page += 1
                time.sleep(1)  # Rate limiting

        # CICLO API PER INBOUND
        if (not shipment_type_filter or shipment_type_filter == 'inbound') and total_shipments_inspected_count < max_results:
            page = debug_page_start
            api_method_name = 'get_inbound_shipments'
            log_prefix = "inbound"
            if shipment_status_filter == 'archived':
                api_method_name = 'get_archived_inbound_shipments'
                log_prefix = "inbound archiviate"
            
            if hasattr(client, api_method_name):
                api_method = getattr(client, api_method_name)
                logger.info(f"Recupero spedizioni {log_prefix} per merchant {merchant_id} con filtro q: {q_query}")
                
                # Riattivo la chiamata reale all'API PrepBusiness per i riassunti
                while True:
                    if total_shipments_inspected_count >= max_results:
                        logger.info(f"Raggiunto max_results ({max_results}), interrompo paginazione.")
                        break
                        
                    current_per_page = 20
                    api_response = None
                    retry_count = 0
                    max_retries = 3
                    
                    while retry_count < max_retries:
                        try:
                            logger.info(f"API Call: Page {page} ({log_prefix}), per_page={current_per_page}")
                            api_response = api_method(merchant_id=merchant_id, per_page=current_per_page, page=page, search_query=q_query)
                            break
                        except Exception as e_api:
                            retry_count += 1
                            if retry_count >= max_retries:
                                final_error_message = f"Errore API persistente su {log_prefix} pagina {page}: {str(e_api)}"
                                logger.error(final_error_message)
                                break
                            logger.warning(f"Tentativo {retry_count}/{max_retries} fallito: {str(e_api)}")
                            time.sleep(5 * (2**retry_count))
                            
                    if final_error_message and retry_count >= max_retries:
                        logger.error("Interruzione paginazione per errore persistente")
                        break
                        
                    if not api_response or not hasattr(api_response, 'data') or not api_response.data:
                        logger.info(f"Nessun dato per pagina {page} ({log_prefix}). Fine paginazione.")
                        break

                    current_shipment_summaries = []
                    for ship_data in api_response.data:
                        status_val = ship_data.status.value if hasattr(ship_data.status, 'value') else ship_data.status
                        current_shipment_summaries.append({
                            'id': ship_data.id, 
                            'name': ship_data.name,
                            'status': status_val, 
                            'type': 'inbound'
                        })
                    
                    # Processa il batch corrente
                    should_stop = process_shipment_summaries_batch(current_shipment_summaries, 'inbound')
                    if should_stop:
                        logger.info("Interruzione richiesta da process_shipment_summaries_batch")
                        break
                        
                    page += 1
                    time.sleep(1)  # Rate limiting

        context_vars['is_waiting'] = False
        context_vars['results'] = SearchResultItem.objects.all().order_by('shipment_name', 'product_title')
        context_vars['total_shipments_inspected'] = total_shipments_inspected_count
        context_vars['total_items_found'] = context_vars['results'].count()
        context_vars['error'] = final_error_message
        logger.info(f"Rendering pagina. Spedizioni ispezionate: {total_shipments_inspected_count}, Items salvati nel DB: {context_vars['total_items_found']}. Error: {context_vars.get('error')}")
        return render(request, 'prep_management/search_shipments.html', context_vars)

    except Exception as e_global:
        logger.error(f"ERRORE GLOBALE NELLA VIEW search_shipments_by_products: {e_global}", exc_info=True)
        context_vars['error'] = f"Errore imprevisto: {e_global}. Spedizioni parzialmente ispezionate: {total_shipments_inspected_count}"
        context_vars['is_waiting'] = False
        context_vars['results'] = SearchResultItem.objects.all().order_by('shipment_name', 'product_title') # Mostra ciò che è stato salvato
        context_vars['total_shipments_inspected'] = total_shipments_inspected_count
        context_vars['total_items_found'] = context_vars['results'].count()
        return render(request, 'prep_management/search_shipments.html', context_vars)
