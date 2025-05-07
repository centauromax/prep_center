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
    """
    View per cercare spedizioni in base a parole chiave nei prodotti e al nome del cliente.
    """
    from libs.prepbusiness.client import PrepBusinessClient
    from libs.config import PREP_BUSINESS_API_KEY, PREP_BUSINESS_API_URL
    
    # Estrai il dominio dall'URL dell'API
    company_domain = PREP_BUSINESS_API_URL.split('//')[-1].split('/')[0]
    
    # Inizializza il client PrepBusiness
    client = PrepBusinessClient(PREP_BUSINESS_API_KEY, company_domain)
    
    # Recupera i parametri dalla richiesta
    keywords = request.GET.get('keywords', '').split(',')
    keywords = [k.strip() for k in keywords if k.strip()]
    search_type = request.GET.get('search_type', 'OR')  # 'AND' o 'OR'
    merchant_name = request.GET.get('merchant_name', '').strip()
    shipment_type = request.GET.get('shipment_type', '').strip()
    shipment_status = request.GET.get('shipment_status', '').strip()
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()
    
    logger.info(f"Parametri di ricerca: keywords={keywords}, search_type={search_type}, merchant_name={merchant_name}, shipment_type={shipment_type}, shipment_status={shipment_status}")
    
    # Recupera tutti i merchant per trovare l'ID del merchant specificato
    merchants = get_merchants()
    merchant_id = None
    if merchant_name:
        merchant = next((m for m in merchants if m['name'].lower() == merchant_name.lower()), None)
        if merchant:
            merchant_id = merchant['id']
            logger.info(f"Merchant trovato: {merchant_name} (ID: {merchant_id})")
    
    # Se non è stato trovato il merchant, mostra un errore
    if merchant_name and not merchant_id:
        logger.warning(f"Merchant non trovato: {merchant_name}")
        context = {
            'error': f'Merchant "{merchant_name}" non trovato',
            'merchants': merchants,
            'title': 'Ricerca spedizioni per prodotti'
        }
        return render(request, 'prep_management/search_shipments.html', context)
    
    # Recupera le spedizioni del merchant in base al tipo selezionato
    shipments = []
    if merchant_id:
        try:
            max_results = int(request.GET.get('max_results', 100))
            # Costruzione della query avanzata q
            q_parts = []
            if shipment_status:
                if shipment_status == 'archived':
                    q_parts.append('status:"archived" OR status:"closed"')
                else:
                    q_parts.append(f'status:"{shipment_status}"')
            if date_from:
                q_parts.append(f'created_at>="{date_from}"')
            if date_to:
                q_parts.append(f'created_at<="{date_to}"')
            if keywords:
                for keyword in keywords:
                    q_parts.append(f'name~"{keyword}"')
            q = ' AND '.join(q_parts) if q_parts else None
            
            # INBOUND
            if not shipment_type or shipment_type == 'inbound':
                inbound_shipments = []
                if shipment_status == 'archived':
                    # Se esiste il metodo per inbound archiviate, usalo
                    if hasattr(client, 'get_archived_inbound_shipments'):
                        logger.info(f"Recupero spedizioni inbound archiviate per merchant {merchant_id} con filtro q: {q}")
                        inbound_response = client.get_archived_inbound_shipments(merchant_id=merchant_id, per_page=max_results, q=q)
                        if hasattr(inbound_response, 'data'):
                            inbound_shipments = inbound_response.data[:max_results]
                    # Altrimenti, non aggiungere nulla
                else:
                    logger.info(f"Recupero spedizioni inbound per merchant {merchant_id} con filtro q: {q}")
                    inbound_response = client.get_inbound_shipments(merchant_id=merchant_id, per_page=max_results, q=q)
                    if hasattr(inbound_response, 'data'):
                        inbound_shipments = inbound_response.data[:max_results]
                for shipment in inbound_shipments:
                    status = shipment.status
                    if status == 'closed':
                        status = 'archived'
                    if shipment_status:
                        if shipment_status == 'archived':
                            if status not in ['archived', 'closed']:
                                continue
                        elif status != shipment_status:
                            continue
                    shipment_dict = {
                        'id': shipment.id,
                        'name': shipment.name,
                        'status': status,
                        'type': 'inbound'
                    }
                    shipments.append(shipment_dict)
                logger.info(f"Trovate {len(shipments)} spedizioni inbound filtrate")
            # OUTBOUND
            if not shipment_type or shipment_type == 'outbound':
                outbound_shipments = []
                if shipment_status == 'archived':
                    logger.info(f"Recupero spedizioni outbound archiviate per merchant {merchant_id} con filtro q: {q}")
                    outbound_response = client.get_archived_outbound_shipments(merchant_id=merchant_id, per_page=max_results, q=q)
                    outbound_shipments = []
                    if hasattr(outbound_response, 'data'):
                        outbound_shipments = outbound_response.data[:max_results]
                else:
                    logger.info(f"Recupero spedizioni outbound per merchant {merchant_id} con filtro q: {q}")
                    outbound_response = client.get_outbound_shipments(merchant_id=merchant_id, per_page=max_results, q=q)
                    outbound_shipments = []
                    if hasattr(outbound_response, 'data'):
                        outbound_shipments = outbound_response.data[:max_results]
                for shipment in outbound_shipments:
                    status = shipment.status
                    if status == 'closed':
                        status = 'archived'
                    if shipment_status:
                        if shipment_status == 'archived':
                            if status not in ['archived', 'closed']:
                                continue
                        elif status != shipment_status:
                            continue
                    shipment_dict = {
                        'id': shipment.id,
                        'name': shipment.name,
                        'status': status,
                        'type': 'outbound'
                    }
                    shipments.append(shipment_dict)
                logger.info(f"Trovate {len(shipments)} spedizioni outbound filtrate")
        except Exception as e:
            logger.error(f"Errore nel recupero delle spedizioni: {str(e)}")
            context = {
                'error': f'Errore nel recupero delle spedizioni: {str(e)}',
                'merchants': merchants,
                'title': 'Ricerca spedizioni per prodotti'
            }
            return render(request, 'prep_management/search_shipments.html', context)
    
    logger.info(f"Totale spedizioni trovate: {len(shipments)}")
    
    # Filtra le spedizioni in base alle parole chiave
    matching_shipments = []
    for shipment in shipments:
        # Recupera i dettagli della spedizione
        try:
            shipment_id = shipment['id']
            shipment_type = shipment['type']
            logger.info(f"Recupero dettagli per spedizione {shipment_id} (tipo: {shipment_type})")
            
            # Usa l'endpoint corretto in base al tipo di spedizione
            if shipment_type == 'inbound':
                details = client.get_inbound_shipment(shipment_id, merchant_id=merchant_id)
                items = client.get_inbound_shipment_items(shipment_id, merchant_id=merchant_id)
            else:  # outbound
                details = client.get_outbound_shipment(shipment_id, merchant_id=merchant_id)
                items = client.get_outbound_shipment_items(shipment_id, merchant_id=merchant_id)
            
            logger.info(f"Trovati {len(items.items)} items per spedizione {shipment_id}")
            
            # Controlla se almeno un prodotto contiene le parole chiave
            matching_items = []
            for item in items.items:
                # DEBUG: logga tutti i campi dell'item per capire la struttura
                if shipment_type == 'outbound':
                    logger.info(f"Item outbound: {vars(item)}")
                # Gestisci il nome del prodotto in base al tipo di spedizione
                if shipment_type == 'inbound':
                    item_name = item.name.lower()
                else:  # outbound
                    # Prendi il titolo dall'oggetto InventoryItem
                    item_name = ''
                    if hasattr(item, 'item') and hasattr(item.item, 'title'):
                        item_name = item.item.title.lower()
                
                if not item_name:  # Salta se non c'è un nome
                    continue
                
                if search_type == 'AND':
                    if all(keyword.lower() in item_name for keyword in keywords):
                        matching_items.append(item)
                        logger.info(f"Item {item_name} corrisponde a tutti i criteri AND")
                else:  # OR
                    if any(keyword.lower() in item_name for keyword in keywords):
                        matching_items.append(item)
                        logger.info(f"Item {item_name} corrisponde ad almeno un criterio OR")
            
            # Se ci sono prodotti che corrispondono, aggiungi la spedizione ai risultati
            if matching_items:
                matching_shipments.append({
                    'shipment': details.shipment,
                    'matching_items': matching_items,
                    'type': shipment_type
                })
                logger.info(f"Spedizione {shipment_id} aggiunta ai risultati con {len(matching_items)} items corrispondenti")
                
        except Exception as e:
            logger.error(f"Errore nel recupero dei dettagli della spedizione {shipment['id']}: {str(e)}")
            continue
    
    logger.info(f"Totale spedizioni corrispondenti: {len(matching_shipments)}")
    
    context = {
        'shipments': matching_shipments,
        'keywords': ', '.join(keywords),
        'search_type': search_type,
        'merchant_name': merchant_name,
        'shipment_type': shipment_type,
        'shipment_status': shipment_status,
        'merchants': merchants,
        'title': 'Ricerca spedizioni per prodotti',
        'max_results': max_results,
        'date_from': date_from,
        'date_to': date_to
    }
    
    return render(request, 'prep_management/search_shipments.html', context)
