from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from .services import PrepBusinessAPI
from .utils.merchants import get_merchants
from .models import ShipmentStatusUpdate, OutgoingMessage, SearchResultItem, IncomingMessage, TelegramNotification, TelegramMessage, AmazonSPAPIConfig
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
# Webhook imports removed temporarily to fix crash
from .event_handlers import WebhookEventProcessor
from django.utils import timezone
from datetime import timedelta, datetime
from libs.prepbusiness.client import PrepBusinessClient
from libs.config import PREP_BUSINESS_API_KEY, PREP_BUSINESS_API_URL
from enum import Enum
from functools import wraps
from typing import Optional, Dict, Any, List
from django.core.cache import cache
# Models import removed temporarily to fix crash
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
from django.db.models import Q
from libs.prepbusiness.client import PrepBusinessClient as OfficialPrepBusinessClient
from libs.config import PREP_BUSINESS_API_URL, PREP_BUSINESS_API_KEY, PREP_BUSINESS_API_TIMEOUT
from .models import PrepBusinessConfig

# 🚀 Import per Amazon SP-API
from libs.api_client.amazon_sp_api import AmazonSPAPIClient, SP_API_AVAILABLE

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
        },
        {
            'name': 'Amazon SP-API',
            'description': 'Integrazione completa con Amazon Selling Partner API. Gestisci ordini, inventario, report e informazioni account Amazon direttamente dalla dashboard.',
            'url': '/prep_management/sp-api/config/',
            'icon': 'fab fa-amazon',
            'color': 'warning',
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

def get_prep_business_client():
    """Helper function to initialize the official client."""
    try:
        domain = PREP_BUSINESS_API_URL.replace('https://', '').split('/api')[0]
        return OfficialPrepBusinessClient(
            api_key=PREP_BUSINESS_API_KEY,
            company_domain=domain,
            timeout=PREP_BUSINESS_API_TIMEOUT
        )
    except Exception as e:
        logger.error(f"Errore inizializzazione client PrepBusiness in views: {e}")
        return None

def merchants_list(request):
    """
    Mostra la lista dei merchants recuperati tramite il client API ufficiale.
    """
    client = get_prep_business_client()
    if not client:
        return render(request, 'prep_management/merchants_list.html', {'error': 'Client API non configurato.'})

    try:
        merchants_response = client.get_merchants() # Get all merchants
        merchants = merchants_response.merchants if merchants_response else []
        
        # Converte i modelli Pydantic in dizionari per il template
        merchants_data = [m.model_dump() for m in merchants]
        
        context = {
            'merchants': merchants_data,
            'merchants_count': len(merchants_data),
        }
    except Exception as e:
        logger.error(f"Errore durante il recupero dei merchants: {e}", exc_info=True)
        context = {'error': str(e)}
        
    return render(request, 'prep_management/merchants_list.html', context)

def api_config_debug(request):
    """
    Mostra una pagina di debug con la configurazione API e lo stato del client ufficiale.
    """
    client = get_prep_business_client()
    config_data = {}
    client_status = {}
    
    # Dati di configurazione
    try:
        from libs.config import get_prep_business_config
        config_data = get_prep_business_config()
    except Exception as e:
        config_data = {'error': str(e)}

    # Stato del client
    if client:
        client_status = {
            'status': '✅ Inizializzato Correttamente',
            'api_key': f"************{client.api_key[-4:]}" if client.api_key else "Non impostata",
            'company_domain': client.company_domain,
            'timeout': client.timeout,
        }
    else:
        client_status = {'status': '❌ Errore di inizializzazione'}
        
    context = {
        'config': config_data,
        'client_status': client_status
    }
    return render(request, 'prep_management/api_config_debug.html', context)


@csrf_exempt
def shipment_status_webhook(request):
    """
    Webhook per ricevere notifiche di cambio stato delle spedizioni.
    
    Questo endpoint riceve notifiche POST quando lo stato di una spedizione cambia.
    Salva i dati ricevuti nel database per essere visualizzati e processati.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method allowed'}, status=405)
    
    try:
        # Parse JSON payload
        import json
        webhook_data = json.loads(request.body.decode('utf-8'))
        
        # Estrai i dati principali dal payload
        # I webhook reali hanno formato: {"data": {...}} senza event_type
        data = webhook_data.get('data', webhook_data)  # Fallback se non c'è 'data'
        
        # Inferisci l'event_type dai dati della spedizione
        def infer_event_type(shipment_data):
            """Inferisce il tipo di evento dai dati della spedizione"""
            status = shipment_data.get('status', '').lower()
            shipped_at = shipment_data.get('shipped_at')
            shipment_id = shipment_data.get('id')
            shipment_name = shipment_data.get('name', '')
            notes = shipment_data.get('notes', '')
            
            # Determina se è inbound o outbound dai campi presenti
            has_outbound_items = 'outbound_items' in shipment_data
            has_inbound_items = 'inbound_items' in shipment_data or 'items' in shipment_data
            
            # CONTROLLO PRIORITARIO: Se è un RESIDUAL o PARTIAL, è sempre INBOUND
            is_residual = 'RESIDUAL' in shipment_name.upper() or 'residual' in notes.lower()
            is_partial = 'PARTIAL' in shipment_name.upper() or 'partial' in notes.lower()
            
            if is_residual or is_partial:
                shipment_type = "RESIDUAL" if is_residual else "PARTIAL"
                logger.info(f"[infer_event_type] 🎯 Shipment {shipment_id}: {shipment_type} rilevato → FORZATO INBOUND")
                # Per i residual e partial, determina solo il tipo di evento inbound
                if status == 'open':
                    return 'inbound_shipment.created'
                elif status == 'received':
                    return 'inbound_shipment.received'
                elif shipped_at:
                    return 'inbound_shipment.shipped'
                else:
                    return 'inbound_shipment.updated'
            
            # MIGLIORAMENTO: Logica più intelligente per riconoscere outbound shipments
            # 1. Se ha outbound_items espliciti
            is_outbound = has_outbound_items
            
            # 2. Se contiene "outbound" nel payload (MA NON nei residual o partial)
            if not is_outbound:
                payload_str = str(shipment_data).lower()
                # Escludi i residual e partial da questa logica
                if 'outbound' in payload_str and not (is_residual or is_partial):
                    is_outbound = True
            
            # 3. Se è status="closed" con shipped_at, probabilmente è outbound
            # (gli inbound raramente hanno status="closed", più spesso "received")
            if not is_outbound and status == 'closed' and shipped_at:
                logger.info(f"[infer_event_type] 🔍 Shipment {shipment_id}: status=closed + shipped_at presente → probabilmente OUTBOUND")
                is_outbound = True
            
            # 4. Controllo più specifico per outbound
            # Se ha ship_from_address_id o è case_forwarding, è probabilmente outbound
            if not is_outbound and ('ship_from_address_id' in shipment_data or 
                                   shipment_data.get('is_case_forwarding') or 
                                   shipment_data.get('is_case_packed')):
                logger.info(f"[infer_event_type] 🔍 Shipment {shipment_id}: caratteristiche outbound specifiche → OUTBOUND")
                is_outbound = True
            
            # Logica per determinare il tipo di evento
            if is_outbound:
                # È una spedizione outbound
                logger.info(f"[infer_event_type] ✅ Shipment {shipment_id} riconosciuto come OUTBOUND (status={status}, shipped_at={bool(shipped_at)})")
                if status == 'open':
                    return 'outbound_shipment.created'
                elif status == 'closed' and shipped_at:
                    return 'outbound_shipment.closed'
                elif shipped_at and not status == 'closed':
                    return 'outbound_shipment.shipped'
                else:
                    return 'outbound_shipment.updated'
            else:
                # È una spedizione inbound (default)
                logger.info(f"[infer_event_type] ✅ Shipment {shipment_id} riconosciuto come INBOUND (status={status}, shipped_at={bool(shipped_at)})")
                if status == 'open':
                    return 'inbound_shipment.created'
                elif status == 'received':
                    return 'inbound_shipment.received'
                elif shipped_at:
                    return 'inbound_shipment.shipped'
                else:
                    return 'inbound_shipment.updated'
        
        # Inferisci l'event_type
        event_type = infer_event_type(data)
        
        logger.info(f"[webhook_parsing] Webhook ricevuto per shipment {data.get('id')}: status={data.get('status')}, shipped_at={data.get('shipped_at')}, inferred_event_type={event_type}")
        
        # Estrai informazioni sui prodotti dal payload per migliorare le notifiche
        def extract_product_info(shipment_data):
            """Estrae informazioni sui prodotti dal payload del webhook"""
            products_info = {}
            
            # Cerca outbound_items
            outbound_items = shipment_data.get('outbound_items', [])
            if outbound_items:
                total_quantity = sum(item.get('quantity', 0) for item in outbound_items)
                products_info['total_quantity'] = total_quantity
                products_info['items_count'] = len(outbound_items)
                products_info['products_summary'] = f"{len(outbound_items)} prodotti, {total_quantity} unità totali"
                logger.info(f"[webhook_products] Trovati {len(outbound_items)} prodotti outbound, {total_quantity} unità totali")
            
            # Cerca inbound_items (se è un inbound)
            inbound_items = shipment_data.get('inbound_items', shipment_data.get('items', []))
            if inbound_items and not outbound_items:  # Solo se non ci sono outbound_items
                total_quantity = sum(item.get('quantity', 0) for item in inbound_items)
                products_info['total_quantity'] = total_quantity
                products_info['items_count'] = len(inbound_items)
                products_info['products_summary'] = f"{len(inbound_items)} prodotti, {total_quantity} unità totali"
                logger.info(f"[webhook_products] Trovati {len(inbound_items)} prodotti inbound, {total_quantity} unità totali")
            
            return products_info
        
        # Estrai info prodotti
        products_info = extract_product_info(data)
        
        # Crea i dati del webhook nel formato atteso (con info prodotti)
        processed_webhook_data = {
            'shipment_id': str(data.get('id')),
            'event_type': event_type,
            'entity_type': 'shipment',
            'previous_status': data.get('previous_status'),  # Potrebbe non essere disponibile
            'new_status': data.get('status', 'unknown'),
            'merchant_id': str(data.get('team_id')) if data.get('team_id') else None,
            'tracking_number': data.get('tracking_number'),
            'carrier': data.get('carrier'),
            'notes': data.get('notes'),
            'payload': webhook_data,
            # Aggiungi informazioni sui prodotti per migliorare le notifiche
            'products_info': products_info
        }
        
        # Crea il processore degli eventi
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

            # 🛡️ DEDUPLICAZIONE INTELLIGENTE: Permetti outbound_shipment.closed sempre
            # Per altri eventi, controlla duplicati solo se arrivano entro 5 minuti
            shipment_id = webhook_data.get('shipment_id')
            event_type = webhook_data.get('event_type', 'other')
            
            # REGOLA SPECIALE: outbound_shipment.closed può sempre essere processato
            # perché può cambiare i prodotti e richiedere nuova creazione di shipment
            if event_type == 'outbound_shipment.closed':
                logger.info(f"[webhook_dedup_smart] ✅ OUTBOUND_CLOSED sempre permesso - shipment_id={shipment_id}")
            else:
                # Per altri eventi, controlla duplicati recenti (ultimi 5 minuti)
                from django.utils import timezone
                from datetime import timedelta
                
                five_minutes_ago = timezone.now() - timedelta(minutes=5)
                recent_webhook = ShipmentStatusUpdate.objects.filter(
                    shipment_id=shipment_id,
                    event_type=event_type,
                    created_at__gte=five_minutes_ago
                ).first()
                
                if recent_webhook:
                    logger.warning(f"[webhook_dedup_smart] 🛡️ WEBHOOK DUPLICATO RECENTE - shipment_id={shipment_id}, event_type={event_type}, existing_id={recent_webhook.id}, created_at={recent_webhook.created_at}")
                    return recent_webhook
                else:
                    logger.info(f"[webhook_dedup_smart] ✅ WEBHOOK PERMESSO - shipment_id={shipment_id}, event_type={event_type} (nessun duplicato recente)")
            
            # Arricchisci il payload con le informazioni sui prodotti (NUOVA FUNZIONALITÀ MANTENUTA)
            enriched_payload = webhook_data.get('payload', {})
            products_info = webhook_data.get('products_info', {})
            if products_info:
                enriched_payload['products_info'] = products_info
                logger.info(f"[webhook_save] Arricchito payload con informazioni prodotti: {products_info}")
            
            # Salva nuovo webhook (sicuro perché abbiamo controllato prima)
            shipment_update = ShipmentStatusUpdate(
                shipment_id=shipment_id,
                event_type=event_type,
                entity_type=webhook_data.get('entity_type', ''),
                previous_status=webhook_data.get('previous_status'),
                new_status=webhook_data.get('new_status', 'other'),
                merchant_id=merchant_id,
                merchant_name=merchant_name,
                tracking_number=webhook_data.get('tracking_number'),
                carrier=webhook_data.get('carrier'),
                notes=webhook_data.get('notes'),
                payload=enriched_payload  # Usa il payload arricchito
            )
            shipment_update.save()
            logger.info(f"[webhook_saved] ✅ NUOVO webhook salvato ID: {shipment_update.id} per shipment_id={shipment_id}, event_type={event_type}")
            
            # Elabora subito l'evento appena salvato
            processor.process_event(shipment_update.id)
            return shipment_update
        
        # Salva e processa il webhook
        saved_update = save_webhook_data(processed_webhook_data)
        
        return JsonResponse({
            'status': 'success',
            'message': 'Webhook processed successfully',
            'update_id': saved_update.id if saved_update else None,
            'event_type': event_type
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON payload'}, status=400)
    except Exception as e:
        logger.error(f"Errore nel processare webhook: {str(e)}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


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
        # company_domain = api_url.split('//')[-1].split('/')[0]
        
        # Crea client PrepBusiness
        client = PrepBusinessClient(
            api_url=api_url,
            api_key=api_key
        )
        
        # Ottieni tutti i merchant
        merchants_response = client.get_merchants()
        merchants = merchants_response.merchants if merchants_response else []
        
        # Estrai info merchant
        merchant_info = []
        for merchant in merchants:
            email = merchant.get('primaryEmail') or merchant.get('email')
            merchant_info.append({
                'id': merchant.get('id'),
                'name': merchant.get('name'),
                'email': email,
                'enabled': merchant.get('enabled', 'N/A')
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
        # webhook_data = WebhookProcessor.parse_payload(test_payload)  # Disabled temporarily
        webhook_data = test_payload  # Use test payload directly
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
            'id': 99999,  # Aggiungi l'attributo id mancante
            'shipment_id': outbound_shipment_id,
            'merchant_id': merchant_id,
            'event_type': 'outbound_shipment.closed',
            'payload': {
                'type': 'outbound_shipment.closed',
                'data': {
                    'id': int(outbound_shipment_id),
                    'name': f'Test Outbound {test_scenario}',
                    'status': 'closed',
                    'team_id': int(merchant_id)
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
            'process_result': result
        })
        
    except Exception as e:
        logger.error(f"[test_residual_inbound_creation] ❌ Errore durante test: {str(e)}")
        logger.exception("Traceback completo:")
        return JsonResponse({
            'success': False,
            'error': str(e),
            'message': 'Errore durante test residual creation'
        }, status=500)

@csrf_exempt
def test_residual_logic_simple(request):
    """
    Test semplificato della logica di calcolo residual per debug.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method allowed'}, status=405)
    
    try:
        # Test con dati hardcoded semplici
        inbound_items = [
            {'sku': 'TEST-SKU-1', 'quantity': 10},
            {'sku': 'TEST-SKU-2', 'quantity': 5},
            {'sku': 'TEST-SKU-3', 'quantity': 8}
        ]
        
        outbound_items = [
            {'sku': 'TEST-SKU-1', 'quantity': 7},
            {'sku': 'TEST-SKU-2', 'quantity': 3}
            # TEST-SKU-3 non presente in outbound
        ]
        
        processor = WebhookEventProcessor()
        residual_items = processor._calculate_residual_items(inbound_items, outbound_items)
        
        return JsonResponse({
            'success': True,
            'inbound_items': inbound_items,
            'outbound_items': outbound_items,
            'residual_items': residual_items,
            'residual_count': len(residual_items),
            'total_residual_quantity': sum(item['quantity'] for item in residual_items)
        })
        
    except Exception as e:
        logger.exception("Errore nel test residual logic:")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@csrf_exempt
def debug_webhook_payload(request, update_id):
    """
    Debug endpoint per visualizzare il payload completo di un webhook.
    """
    try:
        update = ShipmentStatusUpdate.objects.get(id=update_id)
        
        # Estrai informazioni sui prodotti dal payload
        payload = update.payload or {}
        data = payload.get('data', {})
        
        # Cerca outbound_items
        outbound_items = data.get('outbound_items', [])
        products_info = payload.get('products_info', {})
        
        return JsonResponse({
            'success': True,
            'update_id': update_id,
            'shipment_id': update.shipment_id,
            'event_type': update.event_type,
            'merchant_id': update.merchant_id,
            'processed': update.processed,
            'process_success': update.process_success,
            'payload': payload,
            'outbound_items': outbound_items,
            'outbound_items_count': len(outbound_items),
            'total_quantity': sum(item.get('quantity', 0) for item in outbound_items),
            'products_info': products_info,
            'created_at': update.created_at.isoformat()
        }, indent=2)
        
    except ShipmentStatusUpdate.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': f'Webhook update {update_id} not found'
        }, status=404)
    except Exception as e:
        logger.exception(f"Errore nel debug webhook payload {update_id}:")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@api_view(['POST'])
@permission_classes([])
def test_outbound_closed_test2(request):
    """
    Endpoint di test per simulare la chiusura della spedizione "test2".
    Testa il sistema di debug per l'analisi dei prodotti.
    """
    try:
        from .event_handlers import WebhookEventProcessor
        from .models import ShipmentStatusUpdate
        
        # Simula un payload di webhook per outbound_shipment.closed di "test2"
        test_payload = {
            "type": "outbound_shipment.closed",
            "data": {
                "id": 999999999,  # ID sicuramente inesistente
                "name": "test2",
                "status": "closed",
                "team_id": 123,
                "created_at": "2024-01-15T10:00:00Z",
                "updated_at": "2024-01-15T14:30:00Z",
                "shipped_at": "2024-01-15T14:30:00Z",  # Importante per classificazione come 'closed'
                "notes": "Test shipment for debug products analysis",
                "outbound_items": [  # Items da webhook per evitare chiamate API
                    {
                        "item_id": 1001,
                        "quantity": 7,
                        "item": {
                            "merchant_sku": "TEST-SKU-1",
                            "title": "Prodotto Test 1",
                            "asin": "B001TEST1",
                            "fnsku": "X001TEST1"
                        }
                    },
                    {
                        "item_id": 1002,
                        "quantity": 3,
                        "item": {
                            "merchant_sku": "TEST-SKU-2", 
                            "title": "Prodotto Test 2",
                            "asin": "B002TEST2",
                            "fnsku": "X002TEST2"
                        }
                    },
                    {
                        "item_id": 1003,
                        "quantity": 2,
                        "item": {
                            "merchant_sku": "TEST-SKU-3",
                            "title": "Prodotto Test 3", 
                            "asin": "B003TEST3",
                            "fnsku": "X003TEST3"
                        }
                    }
                ]
            }
        }
        
        logger.info(f"[test_outbound_closed_test2] 🎯 Simulazione webhook test2: {test_payload}")
        
        # Crea un record di test nel database
        shipment_update = ShipmentStatusUpdate(
            shipment_id=str(test_payload['data']['id']),
            event_type='outbound_shipment.closed',
            entity_type='outbound_shipment',
            previous_status=None,
            new_status='closed',
            merchant_id=request.data.get('merchant_id', 123),
            merchant_name='Test Merchant',
            tracking_number=None,
            carrier=None,
            notes=f"Test DEBUG per test2 - {timezone.now()}",
            payload=test_payload
        )
        shipment_update.save()
        
        logger.info(f"[test_outbound_closed_test2] 📦 Record creato: ID {shipment_update.id}")
        
        # Elabora l'evento usando il processor
        processor = WebhookEventProcessor()
        result = processor.process_event(shipment_update.id)
        
        logger.info(f"[test_outbound_closed_test2] ✅ Risultato elaborazione: {result}")
        
        return JsonResponse({
            'success': True,
            'message': 'Test spedizione test2 completato - controlla i log per il debug dei prodotti',
            'test_shipment_id': shipment_update.id,
            'processor_result': result,
            'instructions': 'Usa railway logs -s prep_center_backend -d | head -100 per vedere il debug completo',
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.exception("Errore durante il test test2")
        return JsonResponse({
            'success': False,
            'message': f'Errore durante il test test2: {str(e)}',
            'timestamp': timezone.now().isoformat()
        }, status=500)

@api_view(['POST'])
@permission_classes([])
def reprocess_webhook_update(request, update_id):
    """
    Forza il re-processing di un webhook update specifico.
    Utile per debug e testing.
    """
    try:
        from .models import ShipmentStatusUpdate
        from .event_handlers import WebhookEventProcessor
        
        # Trova l'update
        try:
            update = ShipmentStatusUpdate.objects.get(id=update_id)
        except ShipmentStatusUpdate.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': f'Update ID {update_id} non trovato'
            }, status=404)
        
        logger.info(f"[reprocess_webhook_update] 🔄 Re-processing update ID {update_id}: {update.shipment_id} - {update.event_type}")
        
        # Forza il re-processing anche se già processato
        update.processed = False
        update.save()
        
        # Elabora l'evento
        processor = WebhookEventProcessor()
        result = processor.process_event(update_id)
        
        logger.info(f"[reprocess_webhook_update] ✅ Re-processing completato: {result}")
        
        return JsonResponse({
            'success': True,
            'message': f'Re-processing completato per update {update_id}',
            'update_details': {
                'shipment_id': update.shipment_id,
                'event_type': update.event_type,
                'merchant_id': update.merchant_id,
                'created_at': update.created_at.isoformat()
            },
            'processor_result': result,
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.exception(f"Errore nel re-processing update {update_id}")
        return JsonResponse({
            'success': False,
            'message': f'Errore nel re-processing: {str(e)}',
            'timestamp': timezone.now().isoformat()
        }, status=500)

@api_view(['GET'])
@permission_classes([])
def debug_test2_payload(request):
    """
    Debug endpoint per vedere l'ultimo payload test2.
    """
    try:
        from .models import ShipmentStatusUpdate
        
        # Trova l'ultimo update per test2
        last_update = ShipmentStatusUpdate.objects.filter(
            shipment_id=99998,
            event_type='outbound_shipment.closed'
        ).order_by('-created_at').first()
        
        if not last_update:
            return JsonResponse({
                'success': False,
                'message': 'Nessun update test2 trovato'
            })
        
        payload = last_update.payload or {}
        data = payload.get('data', {})
        
        return JsonResponse({
            'success': True,
            'update_id': last_update.id,
            'shipment_id': last_update.shipment_id,
            'event_type': last_update.event_type,
            'payload_keys': list(payload.keys()),
            'data_keys': list(data.keys()),
            'outbound_items_in_data': data.get('outbound_items', []),
            'outbound_items_count': len(data.get('outbound_items', [])),
            'full_payload': payload
        }, indent=2)
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@api_view(['GET'])
@permission_classes([])
def debug_latest_test2_raw(request):
    """
    Debug endpoint per vedere il payload RAW dell'ultimo test2.
    """
    try:
        from .models import ShipmentStatusUpdate
        
        # Trova l'ultimo update con test2 nel nome
        last_update = ShipmentStatusUpdate.objects.filter(
            Q(shipment_id__contains='999999999') | Q(notes__icontains='test2')
        ).order_by('-created_at').first()
        
        if not last_update:
            return JsonResponse({
                'success': False,
                'message': 'Nessun update test2 trovato'
            })
        
        payload = last_update.payload or {}
        
        return JsonResponse({
            'success': True,
            'update_id': last_update.id,
            'shipment_id': last_update.shipment_id,
            'event_type': last_update.event_type,
            'created_at': last_update.created_at.isoformat(),
            'merchant_id': last_update.merchant_id,
            'has_payload': payload is not None,
            'payload_type': str(type(payload)),
            'payload': payload,
            'data_section': payload.get('data', {}) if payload else {},
            'outbound_items_present': 'outbound_items' in payload.get('data', {}) if payload else False,
            'outbound_items_count': len(payload.get('data', {}).get('outbound_items', [])) if payload else 0,
            'outbound_items': payload.get('data', {}).get('outbound_items', []) if payload else []
        }, indent=2)
        
    except Exception as e:
        logger.exception("Errore nel debug latest test2")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@api_view(['GET'])
@permission_classes([AllowAny])
def debug_webhook_processor(request):
    """
    Debug endpoint per verificare lo stato del WebhookEventProcessor
    """
    try:
        # Inizializza il processor
        processor = WebhookEventProcessor()
        
        # Test del client
        client_test = {}
        try:
            merchants = processor.client.get_merchants()
            client_test = {
                'test_successful': True,
                'merchants_count': len(merchants) if merchants else 0,
                'error': None
            }
        except Exception as e:
            client_test = {
                'test_successful': False,
                'merchants_count': 0,
                'error': str(e)
            }
        
        # Statistiche eventi
        total_events = ShipmentStatusUpdate.objects.count()
        unprocessed_events = ShipmentStatusUpdate.objects.filter(processed=False).count()
        outbound_closed_count = ShipmentStatusUpdate.objects.filter(event_type='outbound_shipment.closed').count()
        
        # Ultimi eventi outbound.closed
        recent_outbound_closed = ShipmentStatusUpdate.objects.filter(
            event_type='outbound_shipment.closed'
        ).order_by('-created_at')[:5]
        
        recent_events_data = []
        for event in recent_outbound_closed:
            recent_events_data.append({
                'id': event.id,
                'shipment_id': event.shipment_id,
                'processed': event.processed,
                'process_success': event.process_success,
                'process_message': event.process_message,
                'created_at': event.created_at.isoformat(),
            })
        
        return JsonResponse({
            'client_status': {
                'client_available': processor.client is not None,
                'client_type': type(processor.client).__name__ if processor.client else None,
            },
            'client_test': client_test,
            'debug_info': {
                'total_events': total_events,
                'unprocessed_events': unprocessed_events,
                'outbound_closed_count': outbound_closed_count,
            },
            'recent_outbound_closed_events': recent_events_data,
        })
        
    except Exception as e:
        return JsonResponse({
            'error': str(e),
            'client_status': {
                'client_available': False,
                'client_type': None,
            },
            'client_test': {
                'test_successful': False,
                'error': str(e)
            }
        })


@api_view(['GET'])
@permission_classes([AllowAny])
def debug_webhook_payload_simple(request, update_id):
    """
    Debug endpoint semplice per vedere il payload di un webhook specifico
    """
    try:
        update = ShipmentStatusUpdate.objects.get(id=update_id)
        
        return JsonResponse({
            'update_id': update.id,
            'shipment_id': update.shipment_id,
            'event_type': update.event_type,
            'processed': update.processed,
            'process_success': update.process_success,
            'process_message': update.process_message,
            'payload': update.payload,
            'payload_keys': list(update.payload.keys()) if update.payload else [],
            'payload_has_data': 'data' in (update.payload or {}),
            'payload_root_keys': list(update.payload.keys()) if update.payload else [],
        })
        
    except ShipmentStatusUpdate.DoesNotExist:
        return JsonResponse({'error': f'Webhook update {update_id} not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@api_view(['POST'])
@permission_classes([AllowAny])
def test_outbound_created_with_name(request):
    """
    Test per spedizione in uscita creata con nome della spedizione.
    Verifica che il nome venga estratto correttamente da payload.data.name
    """
    try:
        from .services import send_telegram_notification
        
        # Dati di test per outbound_shipment.created con nome spedizione
        shipment_data = {
            'shipment_id': 'OUTBOUND-TEST-123',
            'shipment_name': 'Test Spedizione con Nome Corretto',
            'notes': 'Test per verificare estrazione nome da payload.data.name',
            'merchant_name': 'Test Merchant'
        }
        
        success = send_telegram_notification(
            email="prep@easyavant.com",
            message=None,  # Formattazione automatica
            event_type="outbound_shipment.created",
            shipment_id=shipment_data['shipment_id'],
            shipment_data=shipment_data
        )
        
        return Response({
            'success': success,
            'message': f'Test outbound created con nome - Success: {success}',
            'data': shipment_data,
            'note': 'Controlla Telegram per verificare che il nome "Test Spedizione con Nome Corretto" sia presente nel messaggio'
        })
        
    except Exception as e:
        import traceback
        return Response({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }, status=500)

@api_view(['GET'])
@permission_classes([AllowAny])
def test_client_get_shipments(request):
    """
    Test per verificare che il metodo get_shipments del client funzioni.
    """
    try:
        from libs.prepbusiness.client import PrepBusinessClient
        
        client = PrepBusinessClient()
        
        # Test con merchant_id specifico
        merchant_id = 7812  # Merchant di test
        
        logger.info(f"[test_client_get_shipments] Test get_shipments per merchant {merchant_id}")
        
        # Testa il metodo get_shipments
        shipments = client.get_shipments(merchant_id=merchant_id)
        
        logger.info(f"[test_client_get_shipments] Recuperate {len(shipments)} spedizioni")
        
        # Filtra solo inbound per il test
        inbound_shipments = [s for s in shipments if s.get('shipment_type') == 'inbound']
        outbound_shipments = [s for s in shipments if s.get('shipment_type') == 'outbound']
        
        # Cerca spedizioni con nome "test2"
        test2_shipments = [s for s in shipments if 'test2' in s.get('name', '').lower()]
        
        return JsonResponse({
            'success': True,
            'message': f'Client get_shipments funziona correttamente',
            'merchant_id': merchant_id,
            'total_shipments': len(shipments),
            'inbound_count': len(inbound_shipments),
            'outbound_count': len(outbound_shipments),
            'test2_shipments': len(test2_shipments),
            'test2_names': [s.get('name') for s in test2_shipments],
            'sample_shipments': shipments[:3] if shipments else []  # Prime 3 per debug
        })
        
    except Exception as e:
        logger.error(f"[test_client_get_shipments] ❌ Errore: {e}")
        logger.exception("Traceback completo:")
        return JsonResponse({
            'success': False,
            'error': str(e),
            'message': 'Errore nel test get_shipments'
        }, status=500)

@api_view(['GET'])
@permission_classes([AllowAny])
def test_client_detailed(request):
    """
    Test dettagliato per verificare tutti i metodi del client PrepBusiness.
    """
    try:
        from libs.prepbusiness.client import PrepBusinessClient
        
        client = PrepBusinessClient()
        
        # Test con merchant_id specifico
        merchant_id = 7812  # Merchant di test
        
        logger.info(f"[test_client_detailed] Test dettagliato per merchant {merchant_id}")
        
        results = {}
        
        # Test 1: get_inbound_shipments
        try:
            inbound_shipments = client.get_inbound_shipments(merchant_id=merchant_id)
            results['inbound_shipments'] = {
                'success': True,
                'count': len(inbound_shipments),
                'sample': inbound_shipments[:2] if inbound_shipments else []
            }
            logger.info(f"[test_client_detailed] ✅ get_inbound_shipments: {len(inbound_shipments)} spedizioni")
        except Exception as e:
            results['inbound_shipments'] = {
                'success': False,
                'error': str(e)
            }
            logger.error(f"[test_client_detailed] ❌ get_inbound_shipments: {e}")
        
        # Test 2: get_outbound_shipments
        try:
            outbound_shipments = client.get_outbound_shipments(merchant_id=merchant_id)
            results['outbound_shipments'] = {
                'success': True,
                'count': len(outbound_shipments),
                'sample': outbound_shipments[:2] if outbound_shipments else []
            }
            logger.info(f"[test_client_detailed] ✅ get_outbound_shipments: {len(outbound_shipments)} spedizioni")
        except Exception as e:
            results['outbound_shipments'] = {
                'success': False,
                'error': str(e)
            }
            logger.error(f"[test_client_detailed] ❌ get_outbound_shipments: {e}")
        
        # Test 3: get_shipments (combinato)
        try:
            all_shipments = client.get_shipments(merchant_id=merchant_id)
            results['get_shipments'] = {
                'success': True,
                'count': len(all_shipments),
                'sample': all_shipments[:2] if all_shipments else []
            }
            logger.info(f"[test_client_detailed] ✅ get_shipments: {len(all_shipments)} spedizioni")
        except Exception as e:
            results['get_shipments'] = {
                'success': False,
                'error': str(e)
            }
            logger.error(f"[test_client_detailed] ❌ get_shipments: {e}")
        
        # Test 4: get_merchants per verificare che il client funzioni
        try:
            merchants = client.get_merchants()
            results['get_merchants'] = {
                'success': True,
                'count': len(merchants),
                'target_merchant_found': any(str(m.get('id')) == str(merchant_id) for m in merchants)
            }
            logger.info(f"[test_client_detailed] ✅ get_merchants: {len(merchants)} merchants")
        except Exception as e:
            results['get_merchants'] = {
                'success': False,
                'error': str(e)
            }
            logger.error(f"[test_client_detailed] ❌ get_merchants: {e}")
        
        return JsonResponse({
            'success': True,
            'message': 'Test dettagliato completato',
            'merchant_id': merchant_id,
            'results': results
        })
        
    except Exception as e:
        logger.error(f"[test_client_detailed] ❌ Errore generale: {e}")
        logger.exception("Traceback completo:")
        return JsonResponse({
            'success': False,
            'error': str(e),
            'message': 'Errore nel test dettagliato'
        }, status=500)

@csrf_exempt
def reprocess_webhook_for_debug(request, update_id):
    """
    Riesegue l'elaborazione di un webhook specifico per il debug.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Usa il metodo POST'}, status=405)
        
    try:
        from .event_handlers import WebhookEventProcessor
        # Aggiungo log extra qui per essere sicuro
        logger.info(f"--- DEBUG REPROCESS: Avvio rielaborazione per Update ID: {update_id} ---")
        
        # Svuoto il risultato precedente per forzare una nuova elaborazione
        update = ShipmentStatusUpdate.objects.get(id=update_id)
        update.processed = False
        update.process_result = {}
        update.save()

        # Eseguo l'elaborazione
        processor = WebhookEventProcessor()
        result = processor.process_event(update_id)
        
        logger.info(f"--- DEBUG REPROCESS: Fine rielaborazione. Risultato: {result} ---")
        
        return JsonResponse(result)
        
    except ShipmentStatusUpdate.DoesNotExist:
        return JsonResponse({'success': False, 'message': f'Update {update_id} non trovato.'}, status=404)
    except Exception as e:
        logger.error(f"Errore durante la rielaborazione di debug: {e}", exc_info=True)
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@api_view(['GET'])
@permission_classes([])
def test_residual_version(request):
    """
    Endpoint per verificare la versione del codice residuale deployato.
    """
    try:
        from datetime import datetime
        from .event_handlers import WebhookEventProcessor
        from .services import format_shipment_notification
        
        # Test semplice senza git
        processor = WebhookEventProcessor()
        
        # Test della logica di calcolo con dati mock
        mock_inbound = [
            {
                'item': {'merchant_sku': 'TEST-001', 'title': 'Prodotto Test 1'},
                'actual': {'quantity': 10},
                'expected': {'quantity': 10}
            },
            {
                'item': {'merchant_sku': 'TEST-002', 'title': 'Prodotto Test 2'},
                'actual': {'quantity': 5},
                'expected': {'quantity': 5}
            }
        ]
        
        mock_outbound = [
            {
                'item': {'merchant_sku': 'TEST-001', 'title': 'Prodotto Test 1'},
                'quantity': 7
            },
            {
                'item': {'merchant_sku': 'TEST-002', 'title': 'Prodotto Test 2'},
                'quantity': 3
            }
        ]
        
        # Test calcolo residuali
        residual_items = processor._calculate_residual_items(mock_inbound, mock_outbound)
        
        # Test formattazione messaggio inbound
        shipment_data = {
            'shipment_id': 'RESIDUAL-123',
            'shipment_name': 'Test Shipment - RESIDUAL',
            'merchant_name': 'Test Merchant',
        }
        
        # Test formattazione in italiano
        message_it = format_shipment_notification(
            event_type='inbound_shipment.created',
            shipment_data=shipment_data,
            user_language='it'
        )
        
        # Test formattazione in inglese
        message_en = format_shipment_notification(
            event_type='inbound_shipment.created',
            shipment_data=shipment_data,
            user_language='en'
        )
        
        return Response({
            'success': True,
            'event_type': 'inbound_shipment.created',
            'test_data': shipment_data,
            'message_it': message_it,
            'message_en': message_en,
            'contains_inbound_it': 'entrata' in message_it.lower(),
            'contains_outbound_it': 'uscita' in message_it.lower(),
            'contains_inbound_en': 'inbound' in message_en.lower(),
            'contains_outbound_en': 'outbound' in message_en.lower(),
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
def get_current_version(request):
    """
    Endpoint per ottenere la versione corrente dell'applicazione.
    """
    try:
        from django.conf import settings
        
        # Leggi la versione dal file scritto all'avvio
        version_file_path = '/tmp/prep_center_version.txt'
        try:
            with open(version_file_path, 'r') as f:
                file_version = f.read().strip()
        except FileNotFoundError:
            file_version = 'file_not_found'
        
        # Versione dal settings
        settings_version = getattr(settings, 'VERSION', 'unknown')
        
        return Response({
            'success': True,
            'version_from_settings': settings_version,
            'version_from_file': file_version,
            'version_file_path': version_file_path,
            'versions_match': settings_version == file_version
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)

@api_view(['GET'])
def version_file(request):
    """
    Endpoint per leggere il file di versione scritto all'avvio
    """
    import os
    
    version_file_path = '/tmp/prep_center_version.txt'
    
    try:
        if os.path.exists(version_file_path):
            with open(version_file_path, 'r') as f:
                version = f.read().strip()
            return HttpResponse(version, content_type='text/plain')
        else:
            return HttpResponse('unknown', content_type='text/plain')
    except Exception as e:
        logger.error(f"Errore lettura file versione: {e}")
        return HttpResponse('error', content_type='text/plain')

@api_view(['POST'])
@permission_classes([])
def test_partial_inbound_creation(request):
    """
    Endpoint di test per simulare la creazione di un inbound partial.
    Testa scenari dove inbound e outbound hanno quantità uguali.
    """
    try:
        # Parametri di test dal request
        outbound_shipment_id = request.data.get('outbound_shipment_id', '88888')
        merchant_id = request.data.get('merchant_id', '123')
        test_scenario = request.data.get('scenario', 'partial_equal')
        
        logger.info(f"[test_partial_inbound_creation] 🧪 Test partial creation - Scenario: {test_scenario}")
        
        # Crea un mock update object per testare il processor
        mock_update = type('MockUpdate', (), {
            'id': 88888,  # ID diverso dai residual
            'shipment_id': outbound_shipment_id,
            'merchant_id': merchant_id,
            'event_type': 'outbound_shipment.closed',
            'payload': {
                'type': 'outbound_shipment.closed',
                'data': {
                    'id': int(outbound_shipment_id),
                    'name': f'Test Partial {test_scenario}',
                    'status': 'closed',
                    'team_id': int(merchant_id)
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
        
        logger.info(f"[test_partial_inbound_creation] 🚀 Inizio elaborazione mock update")
        
        # Esegui il test del processore
        result = processor._process_outbound_shipment_closed(mock_update)
        
        logger.info(f"[test_partial_inbound_creation] 📋 Risultato elaborazione: {result}")
        
        return JsonResponse({
            'success': True,
            'message': 'Test partial inbound creation completato',
            'test_scenario': test_scenario,
            'outbound_shipment_id': outbound_shipment_id,
            'merchant_id': merchant_id,
            'process_result': result
        })
        
    except Exception as e:
        logger.error(f"[test_partial_inbound_creation] ❌ Errore durante test: {str(e)}")
        logger.exception("Traceback completo:")
        return JsonResponse({
            'success': False,
            'error': str(e),
            'message': 'Errore durante test partial creation'
        }, status=500)

@api_view(['POST'])
@permission_classes([])
def test_partial_only_creation(request):
    """
    Test specifico per partial puri (senza residual).
    Simula uno scenario dove tutte le quantità sono uguali.
    """
    try:
        logger.info("[test_partial_only_creation] 🧪 Test PARTIAL PURO - Solo quantità uguali")
        
        # Dati mock per test partial puro
        mock_inbound_items = [
            {
                'item': {'merchant_sku': 'PARTIAL-001', 'title': 'Prodotto Partial 1'},
                'actual': {'quantity': 5},
                'expected': {'quantity': 5}
            },
            {
                'item': {'merchant_sku': 'PARTIAL-002', 'title': 'Prodotto Partial 2'},
                'actual': {'quantity': 3},
                'expected': {'quantity': 3}
            }
        ]
        
        mock_outbound_items = [
            {
                'item': {'merchant_sku': 'PARTIAL-001'},
                'quantity': 5  # Uguale a inbound
            },
            {
                'item': {'merchant_sku': 'PARTIAL-002'},
                'quantity': 3  # Uguale a inbound
            }
        ]
        
        # Test calcolo con processor reale
        from .event_handlers import WebhookEventProcessor
        processor = WebhookEventProcessor()
        
        # Calcola residual (dovrebbe essere vuoto)
        residual_items = processor._calculate_residual_items(mock_inbound_items, mock_outbound_items)
        
        # Calcola partial (dovrebbe trovare tutti gli items)
        partial_items = processor._calculate_partial_items(mock_inbound_items, mock_outbound_items)
        
        # Simula la logica di decisione
        create_residual = len(residual_items) > 0
        create_partial = len(partial_items) > 0 and not create_residual
        
        logger.info(f"[test_partial_only_creation] Residual items: {len(residual_items)}")
        logger.info(f"[test_partial_only_creation] Partial items: {len(partial_items)}")
        logger.info(f"[test_partial_only_creation] Create residual: {create_residual}")
        logger.info(f"[test_partial_only_creation] Create partial: {create_partial}")
        
        return JsonResponse({
            'success': True,
            'test_type': 'partial_only',
            'mock_data': {
                'inbound_items': mock_inbound_items,
                'outbound_items': mock_outbound_items
            },
            'calculation_results': {
                'residual_items': residual_items,
                'residual_count': len(residual_items),
                'partial_items': partial_items,
                'partial_count': len(partial_items)
            },
            'decision_logic': {
                'create_residual': create_residual,
                'create_partial': create_partial,
                'would_create': 'PARTIAL' if create_partial else ('RESIDUAL' if create_residual else 'NOTHING')
            },
            'message': f'Test completato: {"PARTIAL verrebbe creato" if create_partial else "PARTIAL NON verrebbe creato"}'
        })
        
    except Exception as e:
        logger.error(f"[test_partial_only_creation] ❌ Errore: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e),
            'message': 'Errore durante test partial only'
        }, status=500)

@csrf_exempt
def test_outbound_closed_process(request):
    """Endpoint di test per simulare il processo outbound_shipment.closed"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        outbound_id = data.get('outbound_id', 396871)  # Default al più recente
        
        # 🆕 Prima ottieni i dettagli reali dell'outbound
        from libs.prepbusiness.client import PrepBusinessClient
        from .models import PrepBusinessConfig
        from libs.config import PREP_BUSINESS_API_URL, PREP_BUSINESS_API_KEY, PREP_BUSINESS_API_TIMEOUT
        
        # Inizializza client come nell'event processor
        try:
            config = PrepBusinessConfig.objects.filter(is_active=True).first()
            if config and config.api_url and config.api_key:
                domain = config.api_url.replace('https://', '').split('/api')[0]
                client = PrepBusinessClient(api_key=config.api_key, company_domain=domain, timeout=config.api_timeout)
            else:
                domain = PREP_BUSINESS_API_URL.replace('https://', '').split('/api')[0]
                client = PrepBusinessClient(api_key=PREP_BUSINESS_API_KEY, company_domain=domain, timeout=PREP_BUSINESS_API_TIMEOUT)
        except Exception as e:
            logger.error(f"Errore inizializzazione client: {e}")
            return JsonResponse({'error': f'Errore inizializzazione client: {e}'}, status=500)
        
        try:
            # Ottieni dettagli outbound reale
            outbound_details = client.get_outbound_shipment(shipment_id=outbound_id, merchant_id=10096)  # ✅ Merchant ID corretto
            real_name = outbound_details.name if outbound_details else f"Test Outbound {outbound_id}"
            real_team_id = getattr(outbound_details, 'team_id', 10096) if outbound_details else 10096  # ✅ Usa getattr per sicurezza
            real_warehouse_id = getattr(outbound_details, 'warehouse_id', 1) if outbound_details else 1  # ✅ Usa getattr per sicurezza
            
            logger.info(f"🔍 Outbound reale trovato: ID={outbound_id}, Nome='{real_name}', Team={real_team_id}, Warehouse={real_warehouse_id}")
            
        except Exception as e:
            logger.warning(f"⚠️ Impossibile ottenere dettagli outbound {outbound_id}: {e}")
            real_name = f"Test Outbound {outbound_id}"
            real_team_id = 10096  # ✅ Merchant ID corretto
            real_warehouse_id = 1
        
        # Simula un webhook outbound_shipment.closed con dati reali
        webhook_data = {
            "event_type": "outbound_shipment.closed",
            "entity_type": "shipment", 
            "entity_id": str(outbound_id),
            "merchant_id": str(real_team_id),
            "status": "closed",
            "data": {
                "id": outbound_id,
                "name": real_name,  # ✅ Nome reale
                "status": "closed",
                "team_id": real_team_id,  # ✅ Team ID reale
                "warehouse_id": real_warehouse_id  # ✅ Warehouse ID reale
            }
        }
        
        # Crea il record ShipmentStatusUpdate
        update = ShipmentStatusUpdate.objects.create(
            shipment_id=str(outbound_id),  # ✅ Campo corretto
            event_type="outbound_shipment.closed",
            new_status="closed",  # ✅ Campo corretto
            merchant_id=str(real_team_id), 
            entity_type="shipment",
            payload=webhook_data,
            processed=False
        )
        
        # Processa l'evento
        processor = WebhookEventProcessor()
        result = processor.process_event(update.id)
        
        return JsonResponse({
            'success': True,
            'update_id': update.id,
            'result': result,
            'real_outbound_name': real_name,
            'message': f'Test processo outbound_shipment.closed per ID {outbound_id} (nome reale: {real_name})'
        })
        
    except Exception as e:
        logger.error(f"Errore nel test outbound closed: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def debug_last_update(request):
    """Endpoint per vedere i dettagli dell'ultimo ShipmentStatusUpdate processato"""
    try:
        # Prendi l'ultimo update processato
        last_update = ShipmentStatusUpdate.objects.filter(processed=True).order_by('-processed_at').first()
        
        if not last_update:
            return JsonResponse({'error': 'Nessun update processato trovato'}, status=404)
        
        return JsonResponse({
            'update_id': last_update.id,
            'shipment_id': last_update.shipment_id,
            'event_type': last_update.event_type,
            'processed_at': last_update.processed_at.isoformat() if last_update.processed_at else None,
            'process_success': last_update.process_success,
            'process_message': last_update.process_message,
            'process_result': last_update.process_result,  # ✅ Campo corretto
            'payload': last_update.payload
        })
        
    except Exception as e:
        logger.error(f"Errore nel debug last update: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def debug_api_steps(request):
    """Endpoint per testare step by step le API calls per capire quale fallisce"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        outbound_id = data.get('outbound_id', 396871)
        merchant_id = data.get('merchant_id', 1)
        
        from libs.prepbusiness.client import PrepBusinessClient
        from .models import PrepBusinessConfig
        from libs.config import PREP_BUSINESS_API_URL, PREP_BUSINESS_API_KEY, PREP_BUSINESS_API_TIMEOUT
        
        # Inizializza client
        try:
            config = PrepBusinessConfig.objects.filter(is_active=True).first()
            if config and config.api_url and config.api_key:
                domain = config.api_url.replace('https://', '').split('/api')[0]
                client = PrepBusinessClient(api_key=config.api_key, company_domain=domain, timeout=config.api_timeout)
            else:
                domain = PREP_BUSINESS_API_URL.replace('https://', '').split('/api')[0]
                client = PrepBusinessClient(api_key=PREP_BUSINESS_API_KEY, company_domain=domain, timeout=PREP_BUSINESS_API_TIMEOUT)
        except Exception as e:
            return JsonResponse({'error': f'Errore inizializzazione client: {e}'}, status=500)
        
        results = {}
        
        # Step 1: Test get_outbound_shipment
        try:
            results['step1_outbound_details'] = {
                'status': 'testing',
                'description': f'get_outbound_shipment(shipment_id={outbound_id}, merchant_id={merchant_id})'
            }
            outbound_details = client.get_outbound_shipment(shipment_id=outbound_id, merchant_id=merchant_id)
            results['step1_outbound_details'] = {
                'status': 'success',
                'data': {
                    'id': outbound_details.id if outbound_details else None,
                    'name': outbound_details.name if outbound_details else None,
                    'team_id': outbound_details.team_id if outbound_details else None,
                    'warehouse_id': outbound_details.warehouse_id if outbound_details else None
                }
            }
        except Exception as e:
            results['step1_outbound_details'] = {
                'status': 'error',
                'error': str(e)
            }
        
        # Step 2: Test get_outbound_shipment_items
        try:
            results['step2_outbound_items'] = {
                'status': 'testing',
                'description': f'get_outbound_shipment_items(shipment_id={outbound_id}, merchant_id={merchant_id})'
            }
            outbound_items_resp = client.get_outbound_shipment_items(shipment_id=outbound_id, merchant_id=merchant_id)
            items_count = len(outbound_items_resp.items) if outbound_items_resp and outbound_items_resp.items else 0
            results['step2_outbound_items'] = {
                'status': 'success',
                'items_count': items_count,
                'first_item': outbound_items_resp.items[0].model_dump() if items_count > 0 else None
            }
        except Exception as e:
            results['step2_outbound_items'] = {
                'status': 'error',
                'error': str(e)
            }
        
        # Step 3: Test get_inbound_shipments
        try:
            results['step3_inbound_list'] = {
                'status': 'testing',
                'description': f'get_inbound_shipments(merchant_id={merchant_id}, per_page=500)'
            }
            inbound_resp = client.get_inbound_shipments(merchant_id=merchant_id, per_page=500)
            inbound_count = len(inbound_resp.data) if inbound_resp and inbound_resp.data else 0
            results['step3_inbound_list'] = {
                'status': 'success',
                'total_inbounds': inbound_count,
                'first_inbound': {
                    'id': inbound_resp.data[0].id if inbound_count > 0 else None,
                    'name': inbound_resp.data[0].name if inbound_count > 0 else None
                } if inbound_count > 0 else None
            }
        except Exception as e:
            results['step3_inbound_list'] = {
                'status': 'error',
                'error': str(e)
            }
        
        return JsonResponse({
            'success': True,
            'outbound_id': outbound_id,
            'merchant_id': merchant_id,
            'api_tests': results
        })
        
    except Exception as e:
        logger.error(f"Errore nel debug API steps: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def test_partial_submit(request):
    """Test specifico per il submit delle spedizioni PARTIAL"""
    try:
        from libs.prepbusiness.client import PrepBusinessClient
        from libs.prepbusiness.models import Carrier
        from .models import PrepBusinessConfig
        from libs.config import PREP_BUSINESS_API_URL, PREP_BUSINESS_API_KEY, PREP_BUSINESS_API_TIMEOUT
        
        # Inizializza client
        try:
            config = PrepBusinessConfig.objects.filter(is_active=True).first()
            if config and config.api_url and config.api_key:
                domain = config.api_url.replace('https://', '').split('/api')[0]
                client = PrepBusinessClient(api_key=config.api_key, company_domain=domain, timeout=config.api_timeout)
            else:
                domain = PREP_BUSINESS_API_URL.replace('https://', '').split('/api')[0]
                client = PrepBusinessClient(api_key=PREP_BUSINESS_API_KEY, company_domain=domain, timeout=PREP_BUSINESS_API_TIMEOUT)
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Errore inizializzazione client: {e}'}, status=500)
        
        merchant_id = 10096
        
        # Test con le spedizioni PARTIAL create di recente
        partial_shipment_ids = [645327]  # ID dalla log
        
        results = []
        
        for shipment_id in partial_shipment_ids:
            try:
                logger.info(f"🧪 Test submit per PARTIAL shipment {shipment_id}")
                
                # 1. Verifica stato attuale
                shipment_resp = client.get_inbound_shipment(shipment_id=shipment_id, merchant_id=merchant_id)
                current_status = shipment_resp.shipment.status if shipment_resp else "unknown"
                current_shipped_at = getattr(shipment_resp.shipment, 'shipped_at', None) if shipment_resp else None
                
                logger.info(f"📊 Stato attuale shipment {shipment_id}: status={current_status}, shipped_at={current_shipped_at}")
                
                # 2. Esegui submit - Usa solo tracking_numbers=[] (approccio corretto)
                logger.info(f"🚀 Eseguendo submit per shipment {shipment_id} (solo tracking_numbers)...")
                try:
                    submit_resp = client.submit_inbound_shipment(
                        shipment_id=shipment_id,
                        tracking_numbers=[],
                        merchant_id=merchant_id
                    )
                    submit_success = True
                    submit_error = None
                    logger.info(f"✅ Submit completato per shipment {shipment_id}")
                except Exception as e:
                    logger.error(f"❌ Submit fallito: {e}")
                    submit_success = False
                    submit_error = str(e)
                
                # 3. Verifica stato dopo submit solo se submit ha avuto successo
                if submit_success:
                    shipment_resp_after = client.get_inbound_shipment(shipment_id=shipment_id, merchant_id=merchant_id)
                    new_status = shipment_resp_after.shipment.status if shipment_resp_after else "unknown"
                    new_shipped_at = getattr(shipment_resp_after.shipment, 'shipped_at', None) if shipment_resp_after else None
                    
                    logger.info(f"📊 Stato dopo submit shipment {shipment_id}: status={new_status}, shipped_at={new_shipped_at}")
                    
                    results.append({
                        'shipment_id': shipment_id,
                        'before_status': current_status,
                        'before_shipped_at': current_shipped_at,
                        'after_status': new_status,
                        'after_shipped_at': new_shipped_at,
                        'submit_success': True,
                        'status_changed': current_status != new_status
                    })
                else:
                    results.append({
                        'shipment_id': shipment_id,
                        'before_status': current_status,
                        'before_shipped_at': current_shipped_at,
                        'submit_success': False,
                        'submit_error': submit_error
                    })
                
            except Exception as e:
                logger.error(f"❌ Errore nel submit di shipment {shipment_id}: {e}")
                results.append({
                    'shipment_id': shipment_id,
                    'error': str(e),
                    'submit_success': False
                })
        
        return JsonResponse({
            'success': True,
            'message': f'Test submit completato per {len(partial_shipment_ids)} shipments',
            'results': results
        })
        
    except Exception as e:
        logger.error(f"Errore in test_partial_submit: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@csrf_exempt
def test_submit_approaches(request):
    """Test diversi approcci per il submit delle spedizioni PARTIAL"""
    try:
        from libs.prepbusiness.client import PrepBusinessClient
        from libs.prepbusiness.models import Carrier
        from .models import PrepBusinessConfig
        from libs.config import PREP_BUSINESS_API_URL, PREP_BUSINESS_API_KEY, PREP_BUSINESS_API_TIMEOUT
        
        # Inizializza client
        try:
            config = PrepBusinessConfig.objects.filter(is_active=True).first()
            if config and config.api_url and config.api_key:
                domain = config.api_url.replace('https://', '').split('/api')[0]
                client = PrepBusinessClient(api_key=config.api_key, company_domain=domain, timeout=config.api_timeout)
            else:
                domain = PREP_BUSINESS_API_URL.replace('https://', '').split('/api')[0]
                client = PrepBusinessClient(api_key=PREP_BUSINESS_API_KEY, company_domain=domain, timeout=PREP_BUSINESS_API_TIMEOUT)
        except Exception as e:
            return JsonResponse({'error': f'Errore inizializzazione client: {e}'}, status=500)
        
        merchant_id = 10096
        shipment_id = 645327  # ID PARTIAL dalla log
        
        results = []
        
        # Approccio 1: Solo carrier
        try:
            logger.info(f"🧪 Test approccio 1: solo carrier")
            submit_resp = client.submit_inbound_shipment(
                shipment_id=shipment_id,
                carrier=Carrier.NO_TRACKING,
                merchant_id=merchant_id
            )
            results.append({
                'approach': 'solo_carrier',
                'success': True,
                'response': str(submit_resp)
            })
        except Exception as e:
            results.append({
                'approach': 'solo_carrier',
                'success': False,
                'error': str(e)
            })
        
        # Approccio 2: Solo tracking_numbers vuoto
        try:
            logger.info(f"🧪 Test approccio 2: solo tracking_numbers vuoto")
            submit_resp = client.submit_inbound_shipment(
                shipment_id=shipment_id,
                tracking_numbers=[],
                merchant_id=merchant_id
            )
            results.append({
                'approach': 'solo_tracking_numbers',
                'success': True,
                'response': str(submit_resp)
            })
        except Exception as e:
            results.append({
                'approach': 'solo_tracking_numbers',
                'success': False,
                'error': str(e)
            })
        
        return JsonResponse({
            'success': True,
            'shipment_id': shipment_id,
            'results': results
        })
        
    except Exception as e:
        logger.error(f"Errore in test_submit_approaches: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@csrf_exempt
def test_manual_submit(request):
    """
    🆕 Test submit manuale per shipment PARTIAL senza trigger automatico
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method allowed'}, status=405)
    
    try:
        client = get_prep_business_client()
        if not client:
            return JsonResponse({'error': 'Client non configurato'}, status=500)
        
        data = json.loads(request.body)
        shipment_id = data.get('shipment_id')
        
        if not shipment_id:
            return JsonResponse({'error': 'shipment_id required'}, status=400)
        
        logger.info(f"[TEST_MANUAL] Inizio test submit manuale per shipment {shipment_id}")
        
        # 1. Verifica info shipment
        try:
            shipment_response = client.get_shipment(shipment_id)
            shipment = shipment_response.data if hasattr(shipment_response, 'data') else shipment_response
            
            logger.info(f"[TEST_MANUAL] Shipment {shipment_id}: status={shipment.get('status')}, type={shipment.get('type')}")
            
            if shipment.get('status') != 'PARTIAL':
                return JsonResponse({
                    'error': f'Shipment deve essere PARTIAL, attuale: {shipment.get("status")}',
                    'shipment_status': shipment.get('status')
                }, status=400)
                
        except Exception as e:
            logger.error(f"[TEST_MANUAL] Errore verifica shipment {shipment_id}: {e}")
            return JsonResponse({'error': f'Errore verifica shipment: {e}'}, status=500)
        
        # 2. Submit shipment
        try:
            logger.info(f"[TEST_MANUAL] Invio comando submit per shipment {shipment_id}")
            submit_response = client.submit_shipment(shipment_id)
            
            logger.info(f"[TEST_MANUAL] Submit response: {submit_response}")
            
            return JsonResponse({
                'success': True,
                'shipment_id': shipment_id,
                'submit_response': submit_response,
                'message': f'Shipment {shipment_id} sottomesso con successo'
            })
            
        except Exception as e:
            logger.error(f"[TEST_MANUAL] Errore submit shipment {shipment_id}: {e}")
            return JsonResponse({
                'error': f'Errore submit: {e}',
                'shipment_id': shipment_id
            }, status=500)
        
    except Exception as e:
        logger.error(f"[TEST_MANUAL] Errore generale: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


# =============================================================================
# 🚀 AMAZON SP-API VIEWS
# =============================================================================

@api_view(['GET'])
@permission_classes([AllowAny])
def sp_api_config_list(request):
    """Lista delle configurazioni Amazon SP-API."""
    try:
        configs = AmazonSPAPIConfig.objects.all().order_by('marketplace', 'name')
        
        configs_data = []
        for config in configs:
            success_rate = config.get_success_rate()
            
            configs_data.append({
                'id': config.id,
                'name': config.name,
                'marketplace': config.get_marketplace_display(),
                'marketplace_code': config.marketplace,
                'is_active': config.is_active,
                'is_sandbox': config.is_sandbox,
                'last_test_at': config.last_test_at.isoformat() if config.last_test_at else None,
                'last_test_success': config.last_test_success,
                'last_test_message': config.last_test_message,
                'total_api_calls': config.total_api_calls,
                'total_api_errors': config.total_api_errors,
                'success_rate': round(success_rate, 2),
                'created_at': config.created_at.isoformat(),
                'updated_at': config.updated_at.isoformat(),
                # AWS Credentials (masked for security)
                'aws_access_key': config.aws_access_key[:10] + '...' if config.aws_access_key else None,
                'aws_secret_key': '***masked***' if config.aws_secret_key else None,
                'role_arn': config.role_arn,
                'has_aws_credentials': bool(config.aws_access_key and config.aws_secret_key and config.role_arn),
            })
        
        return JsonResponse({
            'success': True,
            'configurations': configs_data,
            'total': len(configs_data),
            'sp_api_available': SP_API_AVAILABLE
        })
        
    except Exception as e:
        logger.error(f"Errore nel recupero configurazioni SP-API: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([AllowAny])
def sp_api_test_connection(request, config_id):
    """Testa la connessione per una configurazione SP-API specifica."""
    try:
        config = AmazonSPAPIConfig.objects.get(id=config_id)
        
        if not SP_API_AVAILABLE:
            config.update_test_result(False, "Libreria SP-API non disponibile")
            return JsonResponse({
                'error': 'Libreria SP-API non disponibile. Installare con: pip install python-amazon-sp-api'
            }, status=500)
        
        # Crea client con le credenziali della configurazione
        credentials = config.get_credentials_dict()
        client = AmazonSPAPIClient(credentials=credentials)
        
        # Test connessione (recupero info account)
        test_result = client.test_connection()
        
        if test_result['success']:
            config.update_test_result(True, test_result['message'])
            return JsonResponse({
                'success': True,
                'message': test_result['message'],
                'account_info': test_result.get('account_info'),
                'test_time': timezone.now().isoformat()
            })
        else:
            config.update_test_result(False, test_result['message'])
            return JsonResponse({
                'success': False,
                'error': test_result['message'],
                'debug_info': test_result.get('debug_info', {}),
                'detailed_errors': test_result.get('detailed_errors', {}),
                'troubleshooting': test_result.get('troubleshooting', {}),
                'lwa_status_code': test_result.get('lwa_status_code'),
                'full_error_data': test_result  # Include tutto per debug completo
            }, status=400)
        
    except AmazonSPAPIConfig.DoesNotExist:
        return JsonResponse({'error': 'Configurazione non trovata'}, status=404)
    except Exception as e:
        logger.error(f"Errore test connessione SP-API: {e}", exc_info=True)
        try:
            config.update_test_result(False, str(e))
        except:
            pass
        return JsonResponse({'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([AllowAny])
def sp_api_orders_list(request):
    """Recupera lista ordini Amazon via SP-API."""
    try:
        # Parametri query
        config_id = request.GET.get('config_id')
        created_after = request.GET.get('created_after')
        created_before = request.GET.get('created_before')
        max_results = int(request.GET.get('max_results', 50))
        
        # Trova configurazione specifica per ID
        if config_id:
            try:
                config = AmazonSPAPIConfig.objects.get(id=config_id)
            except AmazonSPAPIConfig.DoesNotExist:
                return JsonResponse({
                    'error': f'Configurazione {config_id} non trovata'
                }, status=404)
        else:
            # Fallback al vecchio comportamento per marketplace
            marketplace = request.GET.get('marketplace', 'IT')
            config = AmazonSPAPIConfig.get_config_for_marketplace(marketplace)
            if not config:
                return JsonResponse({
                    'error': f'Nessuna configurazione attiva trovata per marketplace {marketplace}'
                }, status=404)
        
        if not SP_API_AVAILABLE:
            return JsonResponse({
                'error': 'Libreria SP-API non disponibile'
            }, status=500)
        
        # Crea client
        credentials = config.get_credentials_dict()
        client = AmazonSPAPIClient(credentials=credentials)
        
        # Calcola date
        if created_after:
            created_after_dt = datetime.fromisoformat(created_after.replace('Z', '+00:00'))
        else:
            # Fallback: ultimi 7 giorni
            created_after_dt = datetime.utcnow() - timedelta(days=7)
            
        if created_before:
            created_before_dt = datetime.fromisoformat(created_before.replace('Z', '+00:00'))
        else:
            created_before_dt = datetime.utcnow()
        
        # Recupera ordini
        orders_data = client.get_orders(
            created_after=created_after_dt,
            created_before=created_before_dt,
            max_results_per_page=max_results
        )
        
        config.increment_api_call_count()
        
        return JsonResponse({
            'success': True,
            'orders': orders_data.get('Orders', []),
            'next_token': orders_data.get('NextToken'),
            'marketplace': config.marketplace,
            'config_used': config.name,
            'config_id': config.id,
            'created_after': created_after_dt.isoformat(),
            'created_before': created_before_dt.isoformat(),
            'total_orders': len(orders_data.get('Orders', [])),
            'total_retrieved': len(orders_data.get('Orders', []))
        })
            
    except Exception as e:
        logger.error(f"Errore recupero ordini SP-API: {e}", exc_info=True)
        try:
            config.increment_api_call_count(is_error=True)
        except:
            pass
        return JsonResponse({'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([AllowAny])
def sp_api_order_detail(request, order_id):
    """Recupera dettagli di un ordine specifico."""
    try:
        config_id = request.GET.get('config_id')
        
        # Trova configurazione specifica per ID
        if config_id:
            try:
                config = AmazonSPAPIConfig.objects.get(id=config_id)
            except AmazonSPAPIConfig.DoesNotExist:
                return JsonResponse({
                    'error': f'Configurazione {config_id} non trovata'
                }, status=404)
        else:
            # Fallback al vecchio comportamento per marketplace
            marketplace = request.GET.get('marketplace', 'IT')
            config = AmazonSPAPIConfig.get_config_for_marketplace(marketplace)
            if not config:
                return JsonResponse({
                    'error': f'Nessuna configurazione attiva trovata per marketplace {marketplace}'
                }, status=404)
        
        if not SP_API_AVAILABLE:
            return JsonResponse({
                'error': 'Libreria SP-API non disponibile'
            }, status=500)
        
        # Crea client
        credentials = config.get_credentials_dict()
        client = AmazonSPAPIClient(credentials=credentials)
        
        # Recupera dettagli ordine
        order_data = client.get_order_details(order_id)
        
        config.increment_api_call_count()
        
        return JsonResponse({
            'success': True,
            'order': order_data,
            'order_id': order_id,
            'marketplace': config.marketplace,
            'config_used': config.name,
            'config_id': config.id
        })
        
    except Exception as e:
        logger.error(f"Errore recupero dettagli ordine {order_id}: {e}", exc_info=True)
        try:
            config.increment_api_call_count(is_error=True)
        except:
            pass
        return JsonResponse({'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([AllowAny])
def sp_api_inventory_summary(request):
    """Recupera riepilogo inventario Amazon."""
    try:
        marketplace = request.GET.get('marketplace', 'IT')
        
        # Trova configurazione attiva
        config = AmazonSPAPIConfig.get_config_for_marketplace(marketplace)
        if not config:
            return JsonResponse({
                'error': f'Nessuna configurazione attiva trovata per marketplace {marketplace}'
            }, status=404)
        
        if not SP_API_AVAILABLE:
            return JsonResponse({
                'error': 'Libreria SP-API non disponibile'
            }, status=500)
        
        # Crea client
        credentials = config.get_credentials_dict()
        client = AmazonSPAPIClient(credentials=credentials)
        
        # Recupera inventario
        inventory_data = client.get_inventory_summary()
        
        config.increment_api_call_count()
        
        return JsonResponse({
            'success': True,
            'inventory': inventory_data,
            'marketplace': marketplace,
            'config_used': config.name
        })
        
    except Exception as e:
        logger.error(f"Errore recupero inventario SP-API: {e}", exc_info=True)
        try:
            config.increment_api_call_count(is_error=True)
        except:
            pass
        return JsonResponse({'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([AllowAny])
def sp_api_reports_list(request):
    """Lista i tipi di report disponibili."""
    try:
        marketplace = request.GET.get('marketplace', 'IT')
        
        # Trova configurazione attiva
        config = AmazonSPAPIConfig.get_config_for_marketplace(marketplace)
        if not config:
            return JsonResponse({
                'error': f'Nessuna configurazione attiva trovata per marketplace {marketplace}'
            }, status=404)
        
        if not SP_API_AVAILABLE:
            return JsonResponse({
                'error': 'Libreria SP-API non disponibile'
            }, status=500)
        
        # Crea client
        credentials = config.get_credentials_dict()
        client = AmazonSPAPIClient(credentials=credentials)
        
        # Lista tipi di report
        report_types = client.get_available_report_types()
        
        config.increment_api_call_count()
        
        return JsonResponse({
            'success': True,
            'report_types': report_types,
            'marketplace': marketplace,
            'config_used': config.name,
            'total_types': len(report_types)
        })
        
    except Exception as e:
        logger.error(f"Errore recupero tipi report SP-API: {e}", exc_info=True)
        try:
            config.increment_api_call_count(is_error=True)
        except:
            pass
        return JsonResponse({'error': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([AllowAny])
def sp_api_create_report(request):
    """Crea un nuovo report."""
    try:
        data = json.loads(request.body) if request.body else {}
        marketplace = data.get('marketplace', 'IT')
        report_type = data.get('report_type')
        
        if not report_type:
            return JsonResponse({'error': 'report_type è richiesto'}, status=400)
        
        # Trova configurazione attiva
        config = AmazonSPAPIConfig.get_config_for_marketplace(marketplace)
        if not config:
            return JsonResponse({
                'error': f'Nessuna configurazione attiva trovata per marketplace {marketplace}'
            }, status=404)
        
        if not SP_API_AVAILABLE:
            return JsonResponse({
                'error': 'Libreria SP-API non disponibile'
            }, status=500)
        
        # Crea client
        credentials = config.get_credentials_dict()
        client = AmazonSPAPIClient(credentials=credentials)
        
        # Parametri opzionali
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        
        # Converti stringhe ISO in datetime se fornite
        if start_time:
            start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        if end_time:
            end_time = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        
        # Crea report
        report_result = client.create_report(
            report_type=report_type,
            start_time=start_time,
            end_time=end_time
        )
        
        config.increment_api_call_count()
        
        return JsonResponse({
            'success': True,
            'report': report_result,
            'marketplace': marketplace,
            'config_used': config.name,
            'report_type': report_type
        })
        
    except Exception as e:
        logger.error(f"Errore creazione report SP-API: {e}", exc_info=True)
        try:
            config.increment_api_call_count(is_error=True)
        except:
            pass
        return JsonResponse({'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([AllowAny])
def sp_api_account_info(request):
    """
    Endpoint per ottenere informazioni account seller Amazon
    """
    try:
        config_id = request.GET.get('config_id')
        if not config_id:
            return JsonResponse({
                'success': False,
                'error': 'config_id parameter required'
            })

        config = get_object_or_404(AmazonSPAPIConfig, id=config_id)
        
        if not SP_API_AVAILABLE:
            return JsonResponse({
                'success': False,
                'error': 'SP-API library not available'
            })
        
        # ✅ CORREZIONE: Passa credenziali come dizionario
        credentials = {
            'refresh_token': config.refresh_token,
            'lwa_app_id': config.lwa_app_id,
            'lwa_client_secret': config.lwa_client_secret,
            'aws_access_key': config.aws_access_key,
            'aws_secret_key': config.aws_secret_key,
            'role_arn': config.role_arn,
            'marketplace': config.marketplace
        }
        
        client = AmazonSPAPIClient(credentials=credentials)
        
        # Ottieni info account
        account_info = client.get_account_info()
        
        # Aggiorna statistiche
        config.increment_api_call_count(success=True)
        
        return JsonResponse({
            'success': True,
            'account_info': account_info,
            'config_name': config.name,
            'marketplace': config.marketplace
        })
        
    except Exception as e:
        logger.error(f"Errore SP-API account info: {e}")
        if 'config' in locals():
            config.increment_api_call_count(success=False)
        
        return JsonResponse({
            'success': False, 
            'error': str(e)
        })

def sp_api_test_orders_page(request):
    """
    Pagina di test user-friendly per testare SP-API orders
    """
    return render(request, 'prep_management/sp_api_test_orders.html')

@api_view(['POST'])
@permission_classes([AllowAny])
def sp_api_test_raw_call(request, config_id):
    """🔍 TEST RAW SP-API: Chiamata diretta con access token per debug"""
    logger.info(f"🔍 SP-API Raw Call Test: config {config_id}")
    
    try:
        config = get_object_or_404(AmazonSPAPIConfig, id=config_id)
        
        # Step 1: Ottieni access token via LWA
        lwa_response = requests.post(
            'https://api.amazon.com/auth/o2/token',
            data={
                'grant_type': 'refresh_token',
                'refresh_token': config.refresh_token,
                'client_id': config.lwa_app_id,
                'client_secret': config.lwa_client_secret
            },
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=30
        )
        
        if lwa_response.status_code != 200:
            return Response({
                'success': False,
                'error': 'LWA Token Exchange failed',
                'lwa_error': lwa_response.text
            }, status=status.HTTP_400_BAD_REQUEST)
        
        lwa_data = lwa_response.json()
        access_token = lwa_data['access_token']
        
        # Step 2: Test chiamata diretta SP-API
        # Proviamo marketplace participation (endpoint più basic)
        
        # Mappa marketplace -> endpoint Amazon
        marketplace_endpoints = {
            'IT': 'https://sellingpartnerapi-eu.amazon.com',
            'DE': 'https://sellingpartnerapi-eu.amazon.com', 
            'FR': 'https://sellingpartnerapi-eu.amazon.com',
            'ES': 'https://sellingpartnerapi-eu.amazon.com',
            'GB': 'https://sellingpartnerapi-eu.amazon.com',
            'US': 'https://sellingpartnerapi-na.amazon.com'
        }
        
        endpoint = marketplace_endpoints.get(config.marketplace, 'https://sellingpartnerapi-eu.amazon.com')
        sp_api_url = f"{endpoint}/sellers/v1/marketplaceParticipations"
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'x-amz-access-token': access_token,
            'Content-Type': 'application/json'
        }
        
        logger.info(f"🔍 Testing direct SP-API call to: {sp_api_url}")
        logger.info(f"🔍 Headers: {headers}")
        
        sp_response = requests.get(
            sp_api_url,
            headers=headers,
            timeout=30
        )
        
        # Risultati del test
        result = {
            'success': sp_response.status_code == 200,
            'lwa_success': True,
            'access_token_length': len(access_token),
            'sp_api_test': {
                'url': sp_api_url,
                'method': 'GET',
                'status_code': sp_response.status_code,
                'headers_sent': headers,
                'response_headers': dict(sp_response.headers),
                'response_body': sp_response.text[:500] + '...' if len(sp_response.text) > 500 else sp_response.text
            },
            'config_info': {
                'marketplace': config.marketplace,
                'endpoint': endpoint,
                'name': config.name
            }
        }
        
        if sp_response.status_code == 200:
            try:
                sp_data = sp_response.json()
                result['sp_api_data'] = sp_data
                result['message'] = '✅ SP-API Raw Call SUCCESS!'
            except:
                result['message'] = '✅ SP-API Call successful but non-JSON response'
        else:
            result['message'] = f'❌ SP-API Call failed: HTTP {sp_response.status_code}'
            result['error_analysis'] = {
                'is_authentication_error': sp_response.status_code == 401,
                'is_authorization_error': sp_response.status_code == 403,
                'is_not_found_error': sp_response.status_code == 404,
                'is_client_error': 400 <= sp_response.status_code < 500,
                'is_server_error': sp_response.status_code >= 500
            }
        
        return Response(result, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"❌ Errore SP-API raw test: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([AllowAny])
def sp_api_test_lwa_only(request, config_id):
    """Testa SOLO l'LWA Token Exchange per una configurazione SP-API specifica."""
    try:
        config = AmazonSPAPIConfig.objects.get(id=config_id)
        
        # Ottieni credenziali
        credentials = config.get_credentials_dict()
        
        # Test LWA Token Exchange diretto
        import requests
        
        logger.info(f"[LWA-TEST] Testing LWA token exchange for config {config_id}")
        
        lwa_response = requests.post(
            'https://api.amazon.com/auth/o2/token',
            data={
                'grant_type': 'refresh_token',
                'refresh_token': credentials.get('refresh_token'),
                'client_id': credentials.get('lwa_app_id'),
                'client_secret': credentials.get('lwa_client_secret')
            },
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=30
        )
        
        response_data = {
            'success': lwa_response.status_code == 200,
            'status_code': lwa_response.status_code,
            'config_used': {
                'id': config.id,
                'name': config.name,
                'marketplace': config.marketplace
            },
            'credentials_summary': {
                'refresh_token': f"{'*' * 10}...{credentials.get('refresh_token', '')[-4:]}" if credentials.get('refresh_token') else 'MISSING',
                'lwa_app_id': credentials.get('lwa_app_id', 'MISSING'),
                'lwa_client_secret': f"{'*' * 10}...{credentials.get('lwa_client_secret', '')[-4:]}" if credentials.get('lwa_client_secret') else 'MISSING'
            }
        }
        
        if lwa_response.status_code == 200:
            lwa_data = lwa_response.json()
            response_data.update({
                'message': 'LWA Token Exchange riuscito!',
                'access_token_present': bool(lwa_data.get('access_token')),
                'token_type': lwa_data.get('token_type'),
                'expires_in': lwa_data.get('expires_in'),
                'scope': lwa_data.get('scope')
            })
        else:
            try:
                error_data = lwa_response.json()
                response_data.update({
                    'message': 'LWA Token Exchange fallito',
                    'error': error_data.get('error', 'Unknown error'),
                    'error_description': error_data.get('error_description', 'No description'),
                    'raw_response': lwa_response.text
                })
            except:
                response_data.update({
                    'message': 'LWA Token Exchange fallito - errore parsing response',
                    'raw_response': lwa_response.text
                })
        
        return JsonResponse(response_data)
        
    except AmazonSPAPIConfig.DoesNotExist:
        return JsonResponse({'error': 'Configurazione non trovata'}, status=404)
    except Exception as e:
        logger.error(f"Errore test LWA: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)

@api_view(['POST'])
@permission_classes([AllowAny])
def sp_api_test_connection(request, config_id):
    """Testa la connessione per una configurazione SP-API specifica."""
    try:
        config = AmazonSPAPIConfig.objects.get(id=config_id)
        
        if not SP_API_AVAILABLE:
            config.update_test_result(False, "Libreria SP-API non disponibile")
            return JsonResponse({
                'error': 'Libreria SP-API non disponibile. Installare con: pip install python-amazon-sp-api'
            }, status=500)
        
        # Crea client con le credenziali della configurazione
        credentials = config.get_credentials_dict()
        client = AmazonSPAPIClient(credentials=credentials)
        
        # Test connessione (recupero info account)
        test_result = client.test_connection()
        
        if test_result['success']:
            config.update_test_result(True, test_result['message'])
            return JsonResponse({
                'success': True,
                'message': test_result['message'],
                'account_info': test_result.get('account_info'),
                'test_time': timezone.now().isoformat()
            })
        else:
            config.update_test_result(False, test_result['message'])
            return JsonResponse({
                'success': False,
                'error': test_result['message'],
                'debug_info': test_result.get('debug_info', {}),
                'detailed_errors': test_result.get('detailed_errors', {}),
                'troubleshooting': test_result.get('troubleshooting', {}),
                'lwa_status_code': test_result.get('lwa_status_code'),
                'full_error_data': test_result  # Include tutto per debug completo
            }, status=400)
        
    except AmazonSPAPIConfig.DoesNotExist:
        return JsonResponse({'error': 'Configurazione non trovata'}, status=404)
    except Exception as e:
        logger.error(f"Errore test connessione SP-API: {e}", exc_info=True)
        try:
            config.update_test_result(False, str(e))
        except:
            pass
        return JsonResponse({'error': str(e)}, status=500)

@api_view(['POST'])
@permission_classes([AllowAny])
def sp_api_debug_advanced(request, config_id):
    """🔍 DEBUG AVANZATO SP-API: Analisi completa per identificare problemi tecnici"""
    logger.info(f"🔍 SP-API Debug Avanzato: Starting analysis for config {config_id}")
    
    if not SP_API_AVAILABLE:
        return Response({
            'success': False,
            'error_type': 'LIBRARY_NOT_AVAILABLE',
            'message': 'SP-API library non installata',
            'install_command': 'pip install python-amazon-sp-api'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    try:
        # Recupera la configurazione
        config = get_object_or_404(AmazonSPAPIConfig, id=config_id)
        if not config.is_active:
            return Response({
                'success': False,
                'error_type': 'CONFIG_INACTIVE',
                'message': f'Configurazione {config_id} non attiva'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Inizializza client con debug avanzato
        credentials = config.get_credentials_dict()
        client = AmazonSPAPIClient(credentials=credentials)
        
        # Esegue debug avanzato
        debug_results = client.debug_connection_advanced()
        
        # Incrementa contatore
        config.total_api_calls += 1
        if not debug_results.get('success'):
            config.total_api_errors += 1
        config.save()
        
        # Log risultati 
        phases = debug_results.get('test_phases', {})
        logger.info(f"🔍 Debug phases: {phases}")
        
        final_analysis = debug_results.get('final_analysis', {})
        main_issue = final_analysis.get('main_issue', 'UNKNOWN')
        logger.info(f"🎯 Main issue identified: {main_issue}")
        
        # Response con tutti i dettagli
        response_data = {
            'config_id': config_id,
            'marketplace': config.marketplace,
            'debug_timestamp': debug_results.get('timestamp'),
            'test_phases': phases,
            'main_issue': main_issue,
            'success': debug_results.get('success', False),
            'detailed_results': debug_results
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except AmazonSPAPIConfig.DoesNotExist:
        return Response({
            'success': False,
            'error_type': 'CONFIG_NOT_FOUND',
            'message': f'Configurazione SP-API {config_id} non trovata'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        logger.error(f"❌ Errore debug avanzato SP-API: {e}", exc_info=True)
        return Response({
            'success': False,
            'error_type': 'DEBUG_EXCEPTION',
            'message': f'Errore durante debug: {str(e)}',
            'traceback': traceback.format_exc()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([AllowAny])
def sp_api_diagnostic_test(request, config_id):
    """Test diagnostico completo per SP-API con diversi marketplace e endpoint."""
    try:
        config = AmazonSPAPIConfig.objects.get(id=config_id)
        credentials = config.get_credentials_dict()
        
        from libs.api_client.amazon_sp_api import AmazonSPAPIClient
        
        results = {
            'config_info': {
                'id': config.id,
                'name': config.name,
                'marketplace': config.get_marketplace_display(),
                'marketplace_code': config.marketplace,
                'is_sandbox': config.is_sandbox
            },
            'lwa_test': {},
            'marketplace_tests': {},
            'api_tests': {}
        }
        
        # Test LWA Token Exchange
        import requests
        try:
            lwa_response = requests.post(
                'https://api.amazon.com/auth/o2/token',
                data={
                    'grant_type': 'refresh_token',
                    'refresh_token': credentials.get('refresh_token'),
                    'client_id': credentials.get('lwa_app_id'),
                    'client_secret': credentials.get('lwa_client_secret')
                },
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=30
            )
            
            if lwa_response.status_code == 200:
                lwa_data = lwa_response.json()
                results['lwa_test'] = {
                    'success': True,
                    'access_token_length': len(lwa_data.get('access_token', '')),
                    'expires_in': lwa_data.get('expires_in'),
                    'token_type': lwa_data.get('token_type')
                }
                access_token = lwa_data.get('access_token')
            else:
                results['lwa_test'] = {
                    'success': False,
                    'status_code': lwa_response.status_code,
                    'error': lwa_response.text
                }
                return JsonResponse(results)
        except Exception as e:
            results['lwa_test'] = {'success': False, 'error': str(e)}
            return JsonResponse(results)
        
        # Test diversi marketplace endpoints
        marketplace_endpoints = {
            'IT': 'https://sellingpartnerapi-eu.amazon.com',
            'ES': 'https://sellingpartnerapi-eu.amazon.com', 
            'FR': 'https://sellingpartnerapi-eu.amazon.com',
            'DE': 'https://sellingpartnerapi-eu.amazon.com',
            'UK': 'https://sellingpartnerapi-eu.amazon.com',
            'US': 'https://sellingpartnerapi-na.amazon.com'
        }
        
        for marketplace, endpoint in marketplace_endpoints.items():
            try:
                # Test marketplace participation per ogni regione
                marketplace_ids = {
                    'IT': 'APJ6JRA9NG5V4',
                    'ES': 'A1RKKUPIHCS9HS', 
                    'FR': 'A13V1IB3VIYZZH',
                    'DE': 'A1PA6795UKMFR9',
                    'UK': 'A1F83G8C2ARO7P',
                    'US': 'ATVPDKIKX0DER'
                }
                
                headers = {
                    'Authorization': f'Bearer {access_token}',
                    'x-amz-access-token': access_token,
                    'Content-Type': 'application/json'
                }
                
                # Test sellers/v1/marketplaceParticipations
                participation_url = f"{endpoint}/sellers/v1/marketplaceParticipations"
                participation_response = requests.get(participation_url, headers=headers, timeout=30)
                
                results['marketplace_tests'][marketplace] = {
                    'endpoint': endpoint,
                    'marketplace_id': marketplace_ids.get(marketplace),
                    'participation_test': {
                        'status_code': participation_response.status_code,
                        'success': participation_response.status_code == 200,
                        'response': participation_response.text[:500] if participation_response.status_code != 200 else 'OK'
                    }
                }
                
                # Se participation funziona, testa orders
                if participation_response.status_code == 200:
                    orders_url = f"{endpoint}/orders/v0/orders"
                    orders_params = {
                        'MarketplaceIds': marketplace_ids.get(marketplace),
                        'CreatedAfter': '2024-01-01T00:00:00Z'
                    }
                    orders_response = requests.get(orders_url, headers=headers, params=orders_params, timeout=30)
                    
                    results['marketplace_tests'][marketplace]['orders_test'] = {
                        'status_code': orders_response.status_code,
                        'success': orders_response.status_code == 200,
                        'response': orders_response.text[:300] if orders_response.status_code != 200 else 'OK'
                    }
                    
            except Exception as e:
                results['marketplace_tests'][marketplace] = {'error': str(e)}
        
        # Test con il client interno
        try:
            credentials = config.get_credentials_dict()
            client = AmazonSPAPIClient(credentials=credentials)
            
            # Test account info
            account_result = client.get_account_info()
            results['api_tests']['account_info'] = {
                'success': account_result.get('success', False),
                'data': account_result.get('data', 'No data'),
                'error': account_result.get('error', 'No error')
            }
            
        except Exception as e:
            results['api_tests'] = {'client_error': str(e)}
        
        return JsonResponse(results, json_dumps_params={'indent': 2})
        
    except AmazonSPAPIConfig.DoesNotExist:
        return JsonResponse({'error': 'Configurazione non trovata'}, status=404)
    except Exception as e:
        logger.error(f"Errore nel test diagnostico SP-API: {e}")
        return JsonResponse({'error': str(e)}, status=500)

@api_view(['POST'])
@permission_classes([AllowAny])
def sp_api_create_us_test_config(request):
    """Crea una configurazione di test per marketplace US usando le stesse credenziali."""
    try:
        # Ottieni la configurazione IT esistente
        it_config = AmazonSPAPIConfig.objects.get(marketplace='IT', is_active=True)
        
        # Verifica se esiste già una config US
        us_config, created = AmazonSPAPIConfig.objects.get_or_create(
            marketplace='US',
            defaults={
                'name': 'US_Test_Config',
                'refresh_token': it_config.refresh_token,
                'lwa_app_id': it_config.lwa_app_id,
                'lwa_client_secret': it_config.lwa_client_secret,
                'api_timeout': it_config.api_timeout,
                'max_retries': it_config.max_retries,
                'is_active': True,
                'is_sandbox': it_config.is_sandbox,
            }
        )
        
        if not created:
            # Se esiste già, aggiorna le credenziali
            us_config.refresh_token = it_config.refresh_token
            us_config.lwa_app_id = it_config.lwa_app_id
            us_config.lwa_client_secret = it_config.lwa_client_secret
            us_config.is_active = True
            us_config.save()
        
        result = {
            'success': True,
            'created': created,
            'us_config': {
                'id': us_config.id,
                'name': us_config.name,
                'marketplace': us_config.get_marketplace_display(),
                'marketplace_code': us_config.marketplace,
                'is_active': us_config.is_active,
                'created_at': us_config.created_at.isoformat(),
                'updated_at': us_config.updated_at.isoformat()
            },
            'it_config_used': {
                'id': it_config.id,
                'name': it_config.name,
                'marketplace': it_config.get_marketplace_display()
            },
            'message': 'Configurazione US creata/aggiornata con successo using credentials from IT config'
        }
        
        return JsonResponse(result, json_dumps_params={'indent': 2})
        
    except AmazonSPAPIConfig.DoesNotExist:
        return JsonResponse({
            'error': 'Configurazione IT non trovata',
            'message': 'È necessaria una configurazione SP-API per marketplace IT per copiare le credenziali'
        }, status=404)
    except Exception as e:
        logger.error(f"Errore creazione config US: {e}")
        return JsonResponse({'error': str(e)}, status=500)

@api_view(['GET'])
@permission_classes([AllowAny])
def sp_api_authorization_status(request):
    """Monitora lo status dell'autorizzazione SP-API per tutti i marketplace configurati."""
    try:
        configs = AmazonSPAPIConfig.objects.filter(is_active=True)
        
        if not configs.exists():
            return JsonResponse({
                'error': 'Nessuna configurazione SP-API attiva trovata'
            }, status=404)
        
        results = {
            'timestamp': timezone.now().isoformat(),
            'configurations': [],
            'overall_status': 'pending',
            'summary': {
                'total_configs': 0,
                'authorized': 0,
                'pending': 0,
                'errors': 0
            }
        }
        
        from libs.api_client.amazon_sp_api import AmazonSPAPIClient
        
        for config in configs:
            config_result = {
                'id': config.id,
                'name': config.name,
                'marketplace': config.get_marketplace_display(),
                'marketplace_code': config.marketplace,
                'last_test_at': config.last_test_at.isoformat() if config.last_test_at else None,
                'last_test_success': config.last_test_success,
                'authorization_status': 'unknown',
                'test_results': {}
            }
            
            # Test rapido solo per marketplace participation (meno invasivo)
            try:
                credentials = config.get_credentials_dict()
                client = AmazonSPAPIClient(credentials=credentials)
                
                # Test connessione completo (include LWA)
                lwa_test = client.test_connection()
                config_result['test_results']['lwa'] = {
                    'success': lwa_test.get('success', False),
                    'message': lwa_test.get('message', 'Test completed'),
                    'debug_info': lwa_test.get('debug_info', {})
                }
                
                if lwa_test.get('success'):
                    # Test solo marketplace participation (rapido)
                    try:
                        participation_info = client.get_marketplace_participation()
                        if participation_info.get('success'):
                            config_result['authorization_status'] = 'authorized'
                            config_result['test_results']['sp_api'] = {
                                'success': True,
                                'message': 'SP-API Authorization ATTIVA!',
                                'data': participation_info.get('data', {})
                            }
                            results['summary']['authorized'] += 1
                        else:
                            config_result['authorization_status'] = 'pending'
                            config_result['test_results']['sp_api'] = {
                                'success': False,
                                'message': 'SP-API ancora non autorizzata',
                                'error': participation_info.get('error', 'Unknown error')
                            }
                            results['summary']['pending'] += 1
                    except Exception as e:
                        if 'Unauthorized' in str(e) or 'Access to requested resource is denied' in str(e):
                            config_result['authorization_status'] = 'pending'
                            config_result['test_results']['sp_api'] = {
                                'success': False,
                                'message': 'SP-API Authorization ancora pending',
                                'error': 'Unauthorized - Waiting for Amazon approval'
                            }
                            results['summary']['pending'] += 1
                        else:
                            config_result['authorization_status'] = 'error'
                            config_result['test_results']['sp_api'] = {
                                'success': False,
                                'message': 'Errore durante test SP-API',
                                'error': str(e)
                            }
                            results['summary']['errors'] += 1
                else:
                    config_result['authorization_status'] = 'error'
                    results['summary']['errors'] += 1
                    
            except Exception as e:
                config_result['authorization_status'] = 'error'
                config_result['test_results']['error'] = str(e)
                results['summary']['errors'] += 1
                
            results['configurations'].append(config_result)
            results['summary']['total_configs'] += 1
        
        # Determina status generale
        if results['summary']['authorized'] > 0:
            results['overall_status'] = 'authorized'
        elif results['summary']['errors'] == results['summary']['total_configs']:
            results['overall_status'] = 'error'
        else:
            results['overall_status'] = 'pending'
            
        # Aggiorna il database con i risultati
        for config_data in results['configurations']:
            try:
                config = configs.get(id=config_data['id'])
                sp_api_result = config_data['test_results'].get('sp_api', {})
                config.update_test_result(
                    success=sp_api_result.get('success', False),
                    message=sp_api_result.get('message', 'Test completed')
                )
            except Exception:
                pass  # Ignore update errors
        
        return JsonResponse(results, json_dumps_params={'indent': 2})
        
    except Exception as e:
        logger.error(f"Errore monitoraggio autorizzazione SP-API: {e}")
        return JsonResponse({'error': str(e)}, status=500)

@api_view(['GET'])
@permission_classes([AllowAny])
def debug_aws_fields(request):
    """Debug endpoint per verificare i campi AWS nel modello."""
    try:
        # Prova a prendere una configurazione esistente
        config = AmazonSPAPIConfig.objects.first()
        if not config:
            return JsonResponse({'error': 'Nessuna configurazione trovata'}, status=404)
        
        # Verifica se i campi AWS esistono nel modello
        debug_info = {
            'config_id': config.id,
            'config_name': config.name,
            'model_fields': [],
            'aws_fields_check': {},
            'migration_status': 'unknown'
        }
        
        # Lista tutti i campi del modello
        for field in config._meta.get_fields():
            debug_info['model_fields'].append({
                'name': field.name,
                'type': type(field).__name__
            })
        
        # Controlla specificamente i campi AWS
        aws_fields = ['aws_access_key', 'aws_secret_key', 'role_arn']
        for field_name in aws_fields:
            try:
                # Prova ad accedere al campo
                value = getattr(config, field_name, 'FIELD_NOT_FOUND')
                debug_info['aws_fields_check'][field_name] = {
                    'exists': hasattr(config, field_name),
                    'value_type': type(value).__name__,
                    'is_none': value is None,
                    'has_value': bool(value) if value != 'FIELD_NOT_FOUND' else False
                }
            except AttributeError as e:
                debug_info['aws_fields_check'][field_name] = {
                    'exists': False,
                    'error': str(e)
                }
        
        return JsonResponse({
            'success': True,
            'debug_info': debug_info
        })
        
    except Exception as e:
        return JsonResponse({
            'error': str(e),
            'error_type': type(e).__name__
        }, status=500)

