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
from .models import ShipmentStatusUpdate
import logging
import requests
import traceback
import json
import os
import hmac
import hashlib
import base64

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
@require_POST
def shipment_status_webhook(request):
    """
    Webhook per ricevere notifiche di cambio stato delle spedizioni.
    
    Questo endpoint riceve notifiche POST quando lo stato di una spedizione cambia.
    Salva i dati ricevuti nel database per essere visualizzati e processati.
    """
    try:
        # Verifica la firma del webhook se impostata una secret key
        webhook_secret = os.environ.get('PREP_BUSINESS_WEBHOOK_SECRET')
        if webhook_secret:
            signature = request.headers.get('X-Webhook-Signature')
            if not verify_webhook_signature(request.body, signature, webhook_secret):
                logger.warning("Firma webhook non valida")
                return HttpResponse("Firma non valida", status=403)
        
        # Leggi i dati JSON
        try:
            data = json.loads(request.body)
            logger.info(f"Webhook ricevuto: {data}")
        except json.JSONDecodeError:
            logger.error(f"Payload webhook non è un JSON valido: {request.body}")
            return HttpResponse("Payload non valido", status=400)
        
        # Verifica che i dati contengano le informazioni necessarie
        shipment_id = data.get('shipment_id')
        new_status = data.get('new_status')
        
        if not shipment_id or not new_status:
            logger.error(f"Dati webhook incompleti: {data}")
            return HttpResponse("Dati incompleti", status=400)
        
        # Mappa lo stato in uno dei nostri stati definiti
        status_map = {
            'pending': 'pending',
            'processing': 'processing',
            'ready': 'ready',
            'shipped': 'shipped',
            'delivered': 'delivered',
            'cancelled': 'cancelled',
            'failed': 'failed',
            'returned': 'returned'
        }
        
        mapped_status = status_map.get(new_status.lower(), 'other')
        previous_status = status_map.get(data.get('previous_status', '').lower(), None)
        
        # Crea il record di aggiornamento
        shipment_update = ShipmentStatusUpdate(
            shipment_id=shipment_id,
            previous_status=previous_status,
            new_status=mapped_status,
            merchant_id=data.get('merchant_id'),
            merchant_name=data.get('merchant_name'),
            tracking_number=data.get('tracking_number'),
            carrier=data.get('carrier'),
            payload=data  # Salva tutto il payload
        )
        shipment_update.save()
        
        logger.info(f"Aggiornamento stato shipment {shipment_id} salvato: {previous_status} → {mapped_status}")
        
        return HttpResponse("OK", status=200)
        
    except Exception as e:
        logger.error(f"Errore durante l'elaborazione del webhook: {str(e)}")
        logger.error(traceback.format_exc())
        return HttpResponse("Errore interno", status=500)


def verify_webhook_signature(payload, signature, secret):
    """
    Verifica la firma HMAC-SHA256 del payload del webhook.
    
    Args:
        payload: Il payload raw della richiesta
        signature: La firma fornita nell'header
        secret: La chiave segreta condivisa
        
    Returns:
        bool: True se la firma è valida, False altrimenti
    """
    if not signature or not secret:
        return False
    
    # Calcola l'HMAC del payload
    computed_signature = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    # Confronta la firma calcolata con quella fornita
    return hmac.compare_digest(computed_signature, signature)


def shipment_status_updates(request):
    """
    View per visualizzare gli aggiornamenti di stato delle spedizioni.
    """
    # Filtri
    status_filter = request.GET.get('status')
    processed_filter = request.GET.get('processed')
    
    # Query base
    updates = ShipmentStatusUpdate.objects.all()
    
    # Applica filtri
    if status_filter:
        updates = updates.filter(new_status=status_filter)
    
    if processed_filter:
        processed = processed_filter.lower() == 'true'
        updates = updates.filter(processed=processed)
    
    # Limita a 100 record per default
    limit = int(request.GET.get('limit', 100))
    updates = updates[:limit]
    
    # Conteggio per status
    status_counts = {}
    for status, _ in ShipmentStatusUpdate.STATUS_CHOICES:
        status_counts[status] = ShipmentStatusUpdate.objects.filter(new_status=status).count()
    
    context = {
        'updates': updates,
        'status_choices': ShipmentStatusUpdate.STATUS_CHOICES,
        'status_counts': status_counts,
        'current_status': status_filter,
        'current_processed': processed_filter,
        'total_updates': ShipmentStatusUpdate.objects.count(),
        'unprocessed_count': ShipmentStatusUpdate.objects.filter(processed=False).count(),
        'title': 'Aggiornamenti stato spedizioni'
    }
    
    return render(request, 'prep_management/shipment_updates.html', context)
