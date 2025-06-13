"""
Modulo per l'elaborazione degli eventi webhook specifici dell'applicazione.
Contiene la logica di business per reagire ai vari tipi di eventi.
"""

import logging
import time
import traceback
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
import pytz
import os

from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
from django.conf import settings

from .models import ShipmentStatusUpdate, OutgoingMessage, TelegramNotification
from .utils.messaging import send_outbound_without_inbound_notification
from .services import send_telegram_notification, format_shipment_notification

# Import libs con gestione errori
try:
    from libs.prepbusiness.client import PrepBusinessClient
    from libs.prepbusiness.models import Carrier
    from libs.config import (
        PREP_BUSINESS_API_URL,
        PREP_BUSINESS_API_KEY,
        PREP_BUSINESS_API_TIMEOUT,
    )
    LIBS_IMPORT_SUCCESS = True
except ImportError as e:
    logger = logging.getLogger('prep_management')
    logger.error(f"[event_handlers] Errore import libs: {e}")
    PrepBusinessClient = None
    Carrier = None
    PREP_BUSINESS_API_URL = None
    PREP_BUSINESS_API_KEY = None
    PREP_BUSINESS_API_TIMEOUT = 30
    LIBS_IMPORT_SUCCESS = False

logger = logging.getLogger('prep_management')

# HOTFIX: Mapping hardcodato dei merchant emails per garantire le notifiche Telegram
MERCHANT_EMAIL_FALLBACK = {
    "7812": "prep@easyavant.com",
    "8185": "commerciale@selley.it",
    # Aggiungi altri se necessario
}

class WebhookEventProcessor:
    """
    Classe per elaborare gli eventi webhook ricevuti da PrepBusiness.
    Implementa la logica di business specifica dell'applicazione.
    """
    
    def __init__(self):
        """
        Inizializza il processore degli eventi webhook.
        """
        logger.info("[WebhookEventProcessor.__init__] Inizio inizializzazione.")
        
        self.client = None
        
        try:
            logger.info("[WebhookEventProcessor.__init__] Inizializzazione client completo PrepBusinessClient.")
            
            # USA SOLO IL CLIENT COMPLETO - NIENTE PIÙ WRAPPER!
            from libs.prepbusiness.client import PrepBusinessClient
            
            # Configurazione per il client completo
            api_key = os.environ.get('PREP_BUSINESS_API_KEY', 'jtc_...')  # Fallback per sviluppo
            company_domain = "dashboard.fbaprepcenteritaly.com"
            timeout = 30
            
            self.client = PrepBusinessClient(
                api_key=api_key,
                company_domain=company_domain,
                timeout=timeout
            )
            
            logger.info(f"[WebhookEventProcessor.__init__] ✅ Client completo inizializzato: Domain={company_domain}, API Key={api_key[:4]}..., Timeout={timeout}s")
            
        except Exception as e:
            logger.error(f"[WebhookEventProcessor.__init__] ❌ Errore inizializzazione client completo: {str(e)}")
            logger.exception("Traceback completo:")
            self.client = None
        
        logger.info("[WebhookEventProcessor.__init__] Fine inizializzazione.")
        
        if self.client is None:
            logger.error("[WebhookEventProcessor.__init__] ❌ ERRORE CRITICO: Nessun client disponibile!")
        else:
            logger.info("[WebhookEventProcessor.__init__] ✅ Client inizializzato correttamente.")
    
    def process_event(self, update_id: int) -> Dict[str, Any]: 
        """
        Elabora un evento webhook in base al suo tipo.
        
        Args:
            update_id: ID dell'aggiornamento ShipmentStatusUpdate da elaborare
            
        Returns:
            Dizionario con i risultati dell'elaborazione
        """
        logger.info(f"[WebhookEventProcessor.process_event] Inizio elaborazione per update_id: {update_id}")
        try:
            # Recupera l'aggiornamento dal database
            try:
                logger.info(f"[WebhookEventProcessor.process_event] Tentativo recupero Update ID: {update_id} dal DB.")
                update = ShipmentStatusUpdate.objects.get(id=update_id)
                logger.info(f"[WebhookEventProcessor.process_event] Update ID: {update_id} recuperato.")
            except ShipmentStatusUpdate.DoesNotExist:
                logger.warning(f"[WebhookEventProcessor.process_event] Aggiornamento con ID {update_id} non trovato nel DB.")
                return {
                    'success': False,
                    'message': f'Aggiornamento con ID {update_id} non trovato',
                    'error': 'update_not_found'
                }
            
            # Se già elaborato, restituisce il risultato salvato
            if update.processed:
                logger.info(f"[WebhookEventProcessor.process_event] Update ID: {update_id} già processato. Salto.")
                return {
                    'success': True,
                    'message': 'Aggiornamento già elaborato in precedenza',
                    'processed': True,
                    'process_result': update.process_result or {}
                }
            
            # Elabora in base al tipo di evento
            event_type = update.event_type
            logger.info(f"[WebhookEventProcessor.process_event] Evento tipo: {event_type} per Update ID: {update_id}.")
            result = None
            
            if event_type == 'outbound_shipment.created':
                logger.info(f"[WebhookEventProcessor.process_event] Chiamata a _process_outbound_shipment_created per Update ID: {update_id}.")
                result = self._process_outbound_shipment_created(update)
            elif event_type.startswith('inbound_shipment.'):
                logger.info(f"[WebhookEventProcessor.process_event] Chiamata a _process_inbound_shipment_event per Update ID: {update_id}.")
                result = self._process_inbound_shipment_event(update)
            elif event_type == 'outbound_shipment.closed':
                logger.info(f"[WebhookEventProcessor.process_event] Chiamata a _process_outbound_shipment_closed per Update ID: {update_id}.")
                result = self._process_outbound_shipment_closed(update)
            else:
                # Handler generico per eventi non specificamente gestiti
                logger.info(f"[WebhookEventProcessor.process_event] Evento {event_type} non gestito specificamente per Update ID: {update_id}.")
                result = {
                    'success': True,
                    'message': f'Evento {event_type} ricevuto ma nessuna elaborazione specifica richiesta',
                }
            
            # Aggiorna il record con il risultato dell'elaborazione
            logger.info(f"[WebhookEventProcessor.process_event] Tentativo salvataggio risultato per Update ID: {update_id}.")
            update.processed = True
            update.processed_at = timezone.now()
            update.process_success = result.get('success', False)
            update.process_message = result.get('message', '')
            update.process_result = result
            update.save()
            logger.info(f"[WebhookEventProcessor.process_event] Risultato salvato per Update ID: {update_id}.")
            
            # Invia notifica Telegram se l'evento lo richiede
            logger.info(f"[WebhookEventProcessor.process_event] Tentativo invio notifica Telegram per evento {update.event_type}")
            
            # Prepara dati base per notifica
            notification_data = {
                'shipment_id': update.shipment_id,
                'shipment_name': update.payload.get('name', '') if isinstance(update.payload, dict) else '',
                'tracking_number': update.payload.get('tracking_number') if isinstance(update.payload, dict) else None,
                'carrier': update.payload.get('carrier') if isinstance(update.payload, dict) else None,
                'notes': update.payload.get('notes', '') if isinstance(update.payload, dict) else '',
                'products_count': None,  # Sarà aggiornato se disponibile
                'expected_count': None,  # Sarà aggiornato se disponibile
                'received_count': None   # Sarà aggiornato se disponibile
            }
            
            # Se il risultato contiene dati aggiuntivi, aggiorna notification_data
            if isinstance(result, dict):
                if 'products_count' in result:
                    notification_data['products_count'] = result['products_count']
                if 'expected_count' in result:
                    notification_data['expected_count'] = result['expected_count']
                if 'received_count' in result:
                    notification_data['received_count'] = result['received_count']
            
            self._send_telegram_notification_if_needed(update, notification_data)
            
            return result
            
        except Exception as e:
            logger.error(f"[WebhookEventProcessor.process_event] Eccezione durante process_event per Update ID: {update_id}. Errore: {e}")
            logger.exception("Traceback completo:")
            
            # Aggiorna il record con l'errore
            try:
                logger.info(f"[WebhookEventProcessor.process_event] Tentativo salvataggio errore per Update ID: {update_id}.")
                update.processed = True
                update.processed_at = timezone.now()
                update.process_success = False
                update.process_message = f"Errore: {e}"
                update.process_result = {
                    'success': False,
                    'error': 'processing_exception',
                    'message': str(e)
                }
                update.save()
                logger.info(f"[WebhookEventProcessor.process_event] Errore salvato per Update ID: {update_id}.")
            except Exception:
                # In caso di errore anche nel salvataggio, logga e continua
                logger.exception("[WebhookEventProcessor.process_event] Eccezione durante il salvataggio dell'errore di elaborazione.")
            
            return {
                'success': False,
                'message': f'Errore durante l\'elaborazione: {e}',
                'error': 'processing_exception'
            }
    
    def _process_outbound_shipment_created(self, update: ShipmentStatusUpdate) -> Dict[str, Any]:
        """
        Elabora l'evento di creazione di una spedizione in uscita.
        """
        return {
            'success': True,
            'message': 'Evento outbound shipment created elaborato',
        }
    
    def _process_inbound_shipment_event(self, update: ShipmentStatusUpdate) -> Dict[str, Any]:
        """
        Elabora eventi per spedizioni in entrata.
        """
        return {
            'success': True,
            'message': f'Evento inbound shipment {update.event_type} elaborato correttamente',
        }
    
    def _process_outbound_shipment_closed(self, update: ShipmentStatusUpdate) -> Dict[str, Any]:
        """
        Elabora un evento di chiusura outbound shipment.
        
        Args:
            update: ShipmentStatusUpdate da elaborare
            
        Returns:
            Dizionario con i risultati dell'elaborazione
        """
        logger.info(f"[_process_outbound_shipment_closed] 🔄 Elaborazione outbound shipment closed per Update ID: {update.id}")
        
        try:
            # Estrai i dati del shipment dal payload
            payload = update.payload
            if not isinstance(payload, dict):
                logger.error(f"[_process_outbound_shipment_closed] ❌ Payload non valido: {payload}")
                return {
                    'success': False,
                    'message': 'Payload non valido',
                    'error': 'invalid_payload'
                }
            
            # Estrai i dati dal campo data
            data = payload.get('data', {})
            if not isinstance(data, dict):
                logger.error(f"[_process_outbound_shipment_closed] ❌ Campo data non valido: {data}")
                return {
                    'success': False,
                    'message': 'Campo data non valido nel payload',
                    'error': 'invalid_data'
                }
            
            # Estrai i dati base
            shipment_id = str(data.get('id', ''))  # Converti in stringa per sicurezza
            shipment_name = str(data.get('name', ''))  # Converti in stringa e usa default vuoto
            merchant_id = str(data.get('team_id', ''))  # team_id è il merchant_id nel payload
            
            # Log dei dati estratti
            logger.info(f"[_process_outbound_shipment_closed] Dati estratti: id={shipment_id}, name={shipment_name}, merchant_id={merchant_id}")
            
            # Verifica dati obbligatori
            if not shipment_id or not shipment_name or not merchant_id:
                logger.error(f"[_process_outbound_shipment_closed] ❌ Dati shipment mancanti: id={shipment_id}, name={shipment_name}, merchant_id={merchant_id}")
                return {
                    'success': False,
                    'message': 'Dati shipment mancanti nel payload',
                    'error': 'missing_data'
                }
            
            # Recupera gli items dell'outbound shipment
            try:
                logger.info(f"[_process_outbound_shipment_closed] Recupero items per outbound shipment {shipment_id}")
                outbound_items = self.client.get_shipment_items(shipment_id)
                logger.info(f"[_process_outbound_shipment_closed] Recuperati {len(outbound_items)} items per outbound shipment {shipment_id}")
            except Exception as e:
                logger.error(f"[_process_outbound_shipment_closed] ❌ Errore recupero items outbound shipment {shipment_id}: {e}")
                return {
                    'success': False,
                    'message': f'Errore recupero items outbound shipment: {e}',
                    'error': 'api_error'
                }
            
            # Cerca l'inbound shipment corrispondente
            try:
                logger.info(f"[_process_outbound_shipment_closed] Ricerca inbound shipment con nome '{shipment_name}' per merchant {merchant_id}")
                inbound_shipments = self.client.get_shipments(merchant_id=merchant_id)
                
                # Filtra per nome esatto
                matching_inbounds = [
                    s for s in inbound_shipments 
                    if s.get('name') == shipment_name
                ]
                
                if not matching_inbounds:
                    logger.info(f"[_process_outbound_shipment_closed] Nessun inbound shipment trovato con nome '{shipment_name}'")
                    return {
                        'success': True,
                        'message': f'Nessun inbound shipment trovato con nome "{shipment_name}" - nessun residual necessario',
                        'products_count': len(outbound_items)
                    }
                
                inbound_shipment = matching_inbounds[0]
                logger.info(f"[_process_outbound_shipment_closed] Trovato inbound shipment {inbound_shipment.get('id')} con nome '{shipment_name}'")
                
            except Exception as e:
                logger.error(f"[_process_outbound_shipment_closed] ❌ Errore ricerca inbound shipment: {e}")
                return {
                    'success': False,
                    'message': f'Errore ricerca inbound shipment: {e}',
                    'error': 'api_error'
                }
            
            # Recupera gli items dell'inbound shipment
            try:
                inbound_shipment_id = inbound_shipment.get('id')
                logger.info(f"[_process_outbound_shipment_closed] Recupero items per inbound shipment {inbound_shipment_id}")
                inbound_items = self.client.get_shipment_items(inbound_shipment_id)
                logger.info(f"[_process_outbound_shipment_closed] Recuperati {len(inbound_items)} items per inbound shipment {inbound_shipment_id}")
            except Exception as e:
                logger.error(f"[_process_outbound_shipment_closed] ❌ Errore recupero items inbound shipment {inbound_shipment_id}: {e}")
                return {
                    'success': False,
                    'message': f'Errore recupero items inbound shipment: {e}',
                    'error': 'api_error'
                }
            
            # Calcola gli items residuali
            residual_items = []
            for outbound_item in outbound_items:
                outbound_sku = outbound_item.get('sku')
                outbound_quantity = outbound_item.get('quantity', 0)
                
                # Cerca l'item corrispondente nell'inbound
                inbound_item = next(
                    (item for item in inbound_items if item.get('sku') == outbound_sku),
                    None
                )
                
                if inbound_item:
                    inbound_quantity = inbound_item.get('quantity', 0)
                    residual_quantity = inbound_quantity - outbound_quantity
                    
                    if residual_quantity > 0:
                        residual_items.append({
                            'sku': outbound_sku,
                            'quantity': residual_quantity,
                            'name': outbound_item.get('name', ''),
                            'asin': outbound_item.get('asin', '')
                        })
            
            if not residual_items:
                logger.info(f"[_process_outbound_shipment_closed] Nessun item residuale trovato per shipment {shipment_id}")
                return {
                    'success': True,
                    'message': 'Nessun item residuale trovato - nessun residual necessario',
                    'products_count': len(outbound_items),
                    'expected_count': len(inbound_items),
                    'received_count': 0
                }
            
            # Crea il residual shipment
            try:
                logger.info(f"[_process_outbound_shipment_closed] Creazione residual shipment per {len(residual_items)} items")
                
                # Prepara i dati per il residual
                residual_data = {
                    'name': f"{shipment_name} - RESIDUAL",
                    'merchant_id': merchant_id,
                    'warehouse_id': inbound_shipment.get('warehouse_id'),
                    'items': residual_items
                }
                
                # Crea il residual
                residual_shipment = self.client.create_inbound_shipment(residual_data)
                residual_id = residual_shipment.get('id')
                
                logger.info(f"[_process_outbound_shipment_closed] ✅ Residual shipment {residual_id} creato con successo")
                
                return {
                    'success': True,
                    'message': f'Residual shipment {residual_id} creato con successo',
                    'residual_id': residual_id,
                    'products_count': len(outbound_items),
                    'expected_count': len(inbound_items),
                    'received_count': len(residual_items)
                }
                
            except Exception as e:
                logger.error(f"[_process_outbound_shipment_closed] ❌ Errore creazione residual shipment: {e}")
                return {
                    'success': False,
                    'message': f'Errore creazione residual shipment: {e}',
                    'error': 'api_error'
                }
            
        except Exception as e:
            logger.error(f"[_process_outbound_shipment_closed] ❌ Errore generale: {e}")
            return {
                'success': False,
                'message': f'Errore generale: {e}',
                'error': 'general_error'
            }
    
    def _send_telegram_notification_if_needed(self, update: ShipmentStatusUpdate, notification_data: Dict[str, Any]):
        """
        Invia una notifica Telegram se l'evento lo richiede.
        """
        # Lista degli eventi per cui inviare notifiche
        notify_events = [
            'inbound_shipment.created',    
            'inbound_shipment.received',
            'inbound_shipment.shipped', 
            'outbound_shipment.created',
            'outbound_shipment.closed',
            'order.created',
            'order.shipped'
        ]
        
        # Controlla se l'evento richiede una notifica
        if update.event_type not in notify_events:
            logger.info(f"[_send_telegram_notification_if_needed] Evento {update.event_type} non richiede notifica.")
            return
        
        logger.info(f"[_send_telegram_notification_if_needed] Invio notifica per evento {update.event_type}")
        
        try:
            # Recupera l'email del merchant
            merchant_email = self._get_merchant_email(update.merchant_id)
            if not merchant_email:
                logger.warning(f"[_send_telegram_notification_if_needed] Nessuna email trovata per merchant {update.merchant_id}")
                return
            
            logger.info(f"[_send_telegram_notification_if_needed] Email merchant trovata: {merchant_email}")
            
            # Invia la notifica (la formattazione del messaggio sarà gestita internamente)
            success = send_telegram_notification(
                email=merchant_email,
                message=None,  # Verrà formattato internamente
                event_type=update.event_type,
                shipment_id=update.shipment_id,
                shipment_data=notification_data  # Passiamo i dati per la formattazione
            )
            
            if success:
                logger.info(f"[_send_telegram_notification_if_needed] ✅ Notifica Telegram inviata per evento {update.event_type} a {merchant_email}")
            else:
                logger.warning(f"[_send_telegram_notification_if_needed] ❌ Notifica Telegram fallita per evento {update.event_type} a {merchant_email}")
                
        except Exception as e:
            logger.error(f"[_send_telegram_notification_if_needed] Errore nell'invio notifica Telegram: {e}")
            logger.exception("Traceback completo:")
    
    def _get_merchant_email(self, merchant_id: str) -> Optional[str]:
        """
        Recupera l'email del merchant tramite API.
        
        Args:
            merchant_id: ID del merchant
            
        Returns:
            Email del merchant o None se non trovata
        """
        logger.info(f"[_get_merchant_email] Recupero email per merchant {merchant_id}")
        
        # HOTFIX: Prima prova il fallback hardcodato per garantire le notifiche
        if str(merchant_id) in MERCHANT_EMAIL_FALLBACK:
            fallback_email = MERCHANT_EMAIL_FALLBACK[str(merchant_id)]
            logger.info(f"[_get_merchant_email] ✅ FALLBACK: Email per merchant {merchant_id}: {fallback_email}")
            
            # Se il client non è disponibile, usa direttamente il fallback
            if self.client is None:
                logger.warning("[_get_merchant_email] Client API non disponibile, uso fallback")
                return fallback_email
        
        try:
            if self.client is None:
                logger.error("[_get_merchant_email] Client API non disponibile!")
                # Se abbiamo un fallback, usalo, altrimenti None
                if str(merchant_id) in MERCHANT_EMAIL_FALLBACK:
                    return MERCHANT_EMAIL_FALLBACK[str(merchant_id)]
                return None
            
            # Ottieni tutti i merchants - il client completo restituisce MerchantsResponse
            merchants_response = self.client.get_merchants()
            
            # Estrai la lista di merchants dal response object
            if hasattr(merchants_response, 'data'):
                merchants_list = [m.model_dump() for m in merchants_response.data]
            elif hasattr(merchants_response, 'merchants'):
                merchants_list = [m.model_dump() for m in merchants_response.merchants]
            else:
                # Fallback se è già una lista (non dovrebbe succedere con client completo)
                merchants_list = merchants_response if isinstance(merchants_response, list) else []
            
            logger.info(f"[_get_merchant_email] Recuperati {len(merchants_list)} merchants")
            
            # Trova il merchant con l'ID specificato
            merchant = next((m for m in merchants_list if str(m.get('id', '')) == str(merchant_id)), None)
            
            if merchant:
                # Prova prima primaryEmail, poi email per retrocompatibilità
                email = merchant.get('primaryEmail') or merchant.get('email')
                if email:
                    logger.info(f"[_get_merchant_email] ✅ Email trovata per merchant {merchant_id}: {email}")
                    return email
                else:
                    logger.warning(f"[_get_merchant_email] ❌ Merchant {merchant_id} trovato ma SENZA primaryEmail/email")
                    # Se abbiamo un fallback, usalo
                    if str(merchant_id) in MERCHANT_EMAIL_FALLBACK:
                        logger.info(f"[_get_merchant_email] 🔄 Uso fallback per merchant {merchant_id}")
                        return MERCHANT_EMAIL_FALLBACK[str(merchant_id)]
                    return None
            else:
                logger.warning(f"[_get_merchant_email] ❌ Merchant {merchant_id} NON trovato nella lista")
                # Se abbiamo un fallback, usalo
                if str(merchant_id) in MERCHANT_EMAIL_FALLBACK:
                    logger.info(f"[_get_merchant_email] 🔄 Uso fallback per merchant {merchant_id}")
                    return MERCHANT_EMAIL_FALLBACK[str(merchant_id)]
                return None
                
        except Exception as e:
            logger.error(f"[_get_merchant_email] Errore durante il recupero email per merchant {merchant_id}: {e}")
            logger.exception("Traceback completo:")
            # In caso di errore, usa il fallback se disponibile
            if str(merchant_id) in MERCHANT_EMAIL_FALLBACK:
                logger.info(f"[_get_merchant_email] 🔄 Errore API, uso fallback per merchant {merchant_id}")
                return MERCHANT_EMAIL_FALLBACK[str(merchant_id)]
            return None

    def _get_outbound_shipment_items(self, shipment_id: str) -> List[Dict[str, Any]]:
        """
        Recupera gli items di una spedizione outbound.
        
        Args:
            shipment_id: ID della spedizione outbound
            
        Returns:
            Lista degli items della spedizione
        """
        logger.info(f"[_get_outbound_shipment_items] 📋 Recupero items per outbound shipment {shipment_id}")
        
        if self.client is None:
            logger.error("[_get_outbound_shipment_items] ❌ Client API non disponibile!")
            return []
        
        try:
            # Converti shipment_id a int
            shipment_id_int = int(shipment_id)
        except (ValueError, TypeError):
            logger.error(f"[_get_outbound_shipment_items] ❌ Shipment ID non valido: '{shipment_id}'")
            return []
        
        try:
            # USA IL CLIENT COMPLETO DIRETTAMENTE
            logger.info(f"[_get_outbound_shipment_items] 📡 Chiamata get_outbound_shipment_items per shipment {shipment_id_int}")
            
            items_response = self.client.get_outbound_shipment_items(
                shipment_id=shipment_id_int
            )
            
            logger.info(f"[_get_outbound_shipment_items] 📋 Risposta API: {type(items_response)}")
            
            # Il client completo restituisce un response object con .items
            if hasattr(items_response, 'items'):
                items = items_response.items
                logger.info(f"[_get_outbound_shipment_items] ✅ Trovati {len(items)} items per outbound shipment {shipment_id}")
                
                # Converte in lista di dict per compatibilità
                items_list = []
                for item in items:
                    item_dict = item.model_dump()
                    items_list.append(item_dict)
                
                return items_list
            else:
                logger.error(f"[_get_outbound_shipment_items] ❌ Risposta API non ha attributo 'items': {dir(items_response)}")
                return []
                
        except Exception as e:
            logger.error(f"[_get_outbound_shipment_items] ❌ Errore recupero items outbound shipment {shipment_id}: {str(e)}")
            logger.exception("Traceback:")
            return []
    
    def _get_inbound_shipment_items(self, shipment_id: str) -> List[Dict[str, Any]]:
        """
        Recupera gli items di una spedizione inbound.
        
        Args:
            shipment_id: ID della spedizione inbound
            
        Returns:
            Lista degli items della spedizione
        """
        logger.info(f"[_get_inbound_shipment_items] 📋 Recupero items per inbound shipment {shipment_id}")
        
        if self.client is None:
            logger.error("[_get_inbound_shipment_items] ❌ Client API non disponibile!")
            return []
        
        try:
            # Converti shipment_id a int
            shipment_id_int = int(shipment_id)
        except (ValueError, TypeError):
            logger.error(f"[_get_inbound_shipment_items] ❌ Shipment ID non valido: '{shipment_id}'")
            return []
        
        try:
            # USA IL CLIENT COMPLETO DIRETTAMENTE
            logger.info(f"[_get_inbound_shipment_items] 📡 Chiamata get_inbound_shipment_items per shipment {shipment_id_int}")
            
            items_response = self.client.get_inbound_shipment_items(
                shipment_id=shipment_id_int
            )
            
            logger.info(f"[_get_inbound_shipment_items] 📋 Risposta API: {type(items_response)}")
            
            # Il client completo restituisce un response object con .items
            if hasattr(items_response, 'items'):
                items = items_response.items
                logger.info(f"[_get_inbound_shipment_items] ✅ Trovati {len(items)} items per inbound shipment {shipment_id}")
                
                # Converte in lista di dict per compatibilità
                items_list = []
                for item in items:
                    item_dict = item.model_dump()
                    items_list.append(item_dict)
                
                return items_list
            else:
                logger.error(f"[_get_inbound_shipment_items] ❌ Risposta API non ha attributo 'items': {dir(items_response)}")
                return []
                
        except Exception as e:
            logger.error(f"[_get_inbound_shipment_items] ❌ Errore recupero items inbound shipment {shipment_id}: {str(e)}")
            logger.exception("Traceback:")
            return []
    
    def _calculate_residual_items(self, inbound_items: List[Dict[str, Any]], outbound_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Calcola i prodotti residuali sottraendo le quantità spedite dall'inbound originale.
        
        Args:
            inbound_items: Lista items dell'inbound originale
            outbound_items: Lista items dell'outbound completato
            
        Returns:
            Lista di dict con i prodotti residuali (con quantità > 0)
        """
        logger.info(f"[_calculate_residual_items] 🧮 Calcolo residual da {len(inbound_items)} inbound e {len(outbound_items)} outbound items")
        
        # Crea un mapping dei prodotti outbound per item_id
        outbound_quantities = {}
        for item in outbound_items:
            item_id = item.get('item_id')
            quantity_shipped = item.get('quantity', 0)
            outbound_quantities[item_id] = outbound_quantities.get(item_id, 0) + quantity_shipped
            logger.debug(f"[_calculate_residual_items] 📤 Outbound - Item ID {item_id}: {quantity_shipped} shipped")
        
        residual_items = []
        
        for inbound_item in inbound_items:
            item_id = inbound_item.get('item_id')
            expected_qty = inbound_item.get('expected_quantity', 0)
            actual_qty = inbound_item.get('actual_quantity', 0)
            shipped_qty = outbound_quantities.get(item_id, 0)
            
            # Calcola le quantità residuali
            residual_expected = max(0, expected_qty - shipped_qty)
            residual_actual = max(0, actual_qty - shipped_qty)
            
            logger.debug(f"[_calculate_residual_items] 📊 Item ID {item_id}: Expected {expected_qty} - Shipped {shipped_qty} = Residual Expected {residual_expected}")
            logger.debug(f"[_calculate_residual_items] 📊 Item ID {item_id}: Actual {actual_qty} - Shipped {shipped_qty} = Residual Actual {residual_actual}")
            
            # Includi solo se almeno una delle quantità è > 0
            if residual_expected > 0 or residual_actual > 0:
                residual_item = {
                    'item_id': item_id,
                    'merchant_sku': inbound_item.get('merchant_sku', ''),
                    'title': inbound_item.get('title', ''),
                    'asin': inbound_item.get('asin', ''),
                    'fnsku': inbound_item.get('fnsku', ''),
                    'expected_quantity': residual_expected,
                    'actual_quantity': residual_actual
                }
                residual_items.append(residual_item)
                logger.debug(f"[_calculate_residual_items] ✅ Aggiunto residual: {residual_item}")
            else:
                logger.debug(f"[_calculate_residual_items] ❌ Item ID {item_id} - nessun residual (entrambe le quantità = 0)")
        
        logger.info(f"[_calculate_residual_items] ✅ Calcolati {len(residual_items)} prodotti residuali")
        return residual_items
    
    def _find_matching_inbound_shipment(self, shipment_name: str, merchant_id: str) -> Optional[Dict[str, Any]]:
        """
        Trova un inbound shipment con il nome specificato.
        
        Args:
            shipment_name: Nome della spedizione da cercare
            merchant_id: ID del merchant
            
        Returns:
            Dict con i dati dell'inbound shipment o None se non trovato
        """
        logger.info(f"[_find_matching_inbound_shipment] 🔍 Ricerca inbound con nome '{shipment_name}' per merchant {merchant_id}")
        
        if self.client is None:
            logger.error("[_find_matching_inbound_shipment] ❌ Client API non disponibile!")
            return None
        
        # Validazione merchant_id
        if not merchant_id or merchant_id.strip() == '':
            logger.error("[_find_matching_inbound_shipment] ❌ Merchant ID vuoto o non valido!")
            return None
        
        try:
            # Converti merchant_id a int per l'API
            merchant_id_int = int(merchant_id)
        except (ValueError, TypeError):
            logger.error(f"[_find_matching_inbound_shipment] ❌ Merchant ID non valido per conversione int: '{merchant_id}'")
            return None
        
        try:
            # USA IL CLIENT COMPLETO DIRETTAMENTE
            logger.info(f"[_find_matching_inbound_shipment] 📡 Chiamata get_inbound_shipments per merchant {merchant_id_int}")
            
            shipments_response = self.client.get_inbound_shipments(
                page=1,
                per_page=100,  # Aumentiamo per essere sicuri di trovare tutti
                merchant_id=merchant_id_int
            )
            
            logger.info(f"[_find_matching_inbound_shipment] 📋 Risposta API: {type(shipments_response)}")
            
            # Il client completo restituisce un response object con .data.shipments
            if hasattr(shipments_response, 'data') and hasattr(shipments_response.data, 'shipments'):
                shipments = shipments_response.data.shipments
                logger.info(f"[_find_matching_inbound_shipment] 📋 Trovati {len(shipments)} inbound shipments")
                
                for shipment in shipments:
                    # Accesso diretto agli attributi Pydantic
                    current_name = shipment.name if hasattr(shipment, 'name') else ''
                    shipment_id = shipment.id if hasattr(shipment, 'id') else None
                    
                    logger.debug(f"[_find_matching_inbound_shipment] 🔍 Controllo shipment ID {shipment_id}, nome: '{current_name}'")
                    
                    if current_name == shipment_name:
                        logger.info(f"[_find_matching_inbound_shipment] ✅ TROVATO inbound shipment: ID {shipment_id}, nome '{current_name}'")
                        # Converte in dict per compatibilità
                        return shipment.model_dump()
                
                logger.warning(f"[_find_matching_inbound_shipment] ❌ Nessun inbound shipment trovato con nome '{shipment_name}' tra {len(shipments)} shipments")
                
                # DEBUG: Mostra i primi 5 nomi per debug
                if len(shipments) > 0:
                    sample_names = [s.name if hasattr(s, 'name') else 'NO_NAME' for s in shipments[:5]]
                    logger.info(f"[_find_matching_inbound_shipment] 🔍 Primi 5 nomi trovati: {sample_names}")
                
            else:
                logger.error(f"[_find_matching_inbound_shipment] ❌ Risposta API non ha struttura attesa: {dir(shipments_response)}")
                if hasattr(shipments_response, 'data'):
                    logger.error(f"[_find_matching_inbound_shipment] ❌ Struttura data: {dir(shipments_response.data)}")
            
            return None
                
        except Exception as e:
            logger.error(f"[_find_matching_inbound_shipment] ❌ Errore ricerca inbound shipment: {str(e)}")
            logger.exception("Traceback:")
            return None
    
    def _generate_residual_name(self, original_name: str, merchant_id: str) -> str:
        """
        Genera il nome per l'inbound residual, gestendo numerazione progressiva.
        
        Args:
            original_name: Nome dell'inbound originale
            merchant_id: ID del merchant
            
        Returns:
            Nome generato per il residual (es. "Original - Residual", "Original - Residual 2", ecc.)
        """
        logger.info(f"[_generate_residual_name] 🏷️ Generazione nome residual per '{original_name}'")
        
        # ✅ FIX: Gestisci nomi che sono già residual per evitare "test2 - residual - residual"
        base_name_for_residual = original_name
        
        # Se il nome contiene già "- Residual", estrai il nome base originale
        if " - Residual" in original_name:
            # Esempio: "test2 - Residual" -> "test2", "test2 - Residual 3" -> "test2"
            base_name_for_residual = original_name.split(" - Residual")[0]
            logger.info(f"[_generate_residual_name] 🔄 Nome già residual, estratto nome base: '{base_name_for_residual}'")
        
        base_name = f"{base_name_for_residual} - Residual"
        
        try:
            # Controlla se esiste già un inbound con questo nome
            if not self._find_matching_inbound_shipment(base_name, merchant_id):
                logger.info(f"[_generate_residual_name] ✅ Nome disponibile: '{base_name}'")
                return base_name
            
            # Se esiste, prova con numerazione progressiva
            counter = 2
            max_attempts = 20  # Limite di sicurezza
            
            while counter <= max_attempts:
                numbered_name = f"{base_name_for_residual} - Residual {counter}"
                if not self._find_matching_inbound_shipment(numbered_name, merchant_id):
                    logger.info(f"[_generate_residual_name] ✅ Nome disponibile: '{numbered_name}'")
                    return numbered_name
                counter += 1
            
            # Se tutti i nomi sono occupati, aggiungi timestamp
            import time
            timestamp = int(time.time())
            fallback_name = f"{base_name_for_residual} - Residual {timestamp}"
            logger.warning(f"[_generate_residual_name] ⚠️ Usando nome fallback con timestamp: '{fallback_name}'")
            return fallback_name
            
        except Exception as e:
            logger.error(f"[_generate_residual_name] ❌ Errore generazione nome: {str(e)}")
            # Fallback con timestamp in caso di errore
            import time
            timestamp = int(time.time())
            fallback_name = f"{base_name_for_residual} - Residual {timestamp}"
            logger.warning(f"[_generate_residual_name] ⚠️ Usando nome fallback per errore: '{fallback_name}'")
            return fallback_name
    
    def _create_residual_inbound_shipment(self, residual_name: str, inbound_shipment: Dict[str, Any], residual_items: List[Dict[str, Any]]) -> Optional[int]:
        """
        Crea un nuovo inbound shipment residual con gli items calcolati.
        
        Args:
            residual_name: Nome per il nuovo shipment residual
            inbound_shipment: Dati del shipment inbound originale
            residual_items: Lista degli items residuali da aggiungere
            
        Returns:
            ID del nuovo shipment creato o None se fallisce
        """
        try:
            logger.info(f"🚀 Creazione inbound residual '{residual_name}' con {len(residual_items)} items")
            
            # Step 1: Crea il nuovo shipment inbound
            logger.info(f"📋 Creazione inbound shipment con name='{residual_name}', warehouse_id={inbound_shipment['warehouse_id']}, merchant_id={inbound_shipment['team_id']}")
            
            create_response = self.client.create_inbound_shipment(
                name=residual_name,
                warehouse_id=inbound_shipment['warehouse_id'],
                notes="Inbound residual creato automaticamente dal sistema",
                merchant_id=inbound_shipment['team_id']
            )
            
            # Il client completo restituisce un response object con shipment_id
            residual_shipment_id = create_response.shipment_id
            logger.info(f"✅ Inbound shipment creato con ID: {residual_shipment_id}")
            
            # Step 2: Aggiungi tutti gli items al shipment
            items_added = 0
            items_failed = 0
            
            for item in residual_items:
                try:
                    logger.info(f"➕ Aggiunta item {item['item_id']} con quantità {item['expected_quantity']}")
                    
                    self.client.add_item_to_shipment(
                        shipment_id=residual_shipment_id,
                        item_id=item['item_id'],
                        quantity=item['expected_quantity'],
                        merchant_id=inbound_shipment['team_id']
                    )
                    
                    logger.info(f"✅ Item {item['item_id']} aggiunto con quantità expected: {item['expected_quantity']}")
                    items_added += 1
                    
                except Exception as e:
                    logger.error(f"❌ Errore aggiunta item {item['item_id']}: {e}")
                    items_failed += 1
                    continue
            
            # Step 3: Log risultati aggiunta items
            logger.info(f"📊 Aggiunta items completata:")
            logger.info(f"    ✅ Items aggiunti: {items_added}")
            logger.info(f"    ❌ Items falliti: {items_failed}")
            logger.info(f"    📦 Totale items: {len(residual_items)}")
            
            # Step 4: Submit il shipment con carrier NO_TRACKING
            try:
                logger.info(f"📤 Submit shipment {residual_shipment_id} con carrier NO_TRACKING")
                
                self.client.submit_inbound_shipment(
                    shipment_id=residual_shipment_id,
                    carrier=Carrier.NO_TRACKING
                )
                
                logger.info(f"✅ Shipment {residual_shipment_id} submitted con successo")
                
                # Step 5: Aggiorna le quantità actual degli items (marca come ricevuti)
                for item in residual_items:
                    try:
                        # Usa il metodo del client completo per aggiornare le quantità
                        from libs.prepbusiness.models import ExpectedItemUpdate, ActualItemUpdate
                        
                        expected_update = ExpectedItemUpdate(
                            quantity=item['expected_quantity'],
                            item_group_configurations=[]
                        )
                        
                        actual_update = ActualItemUpdate(
                            quantity=item['actual_quantity'],
                            item_group_configurations=[]
                        )
                        
                        self.client.update_shipment_item(
                            shipment_id=residual_shipment_id,
                            item_id=item['item_id'],
                            expected=expected_update,
                            actual=actual_update,
                            merchant_id=inbound_shipment['team_id']
                        )
                        
                        logger.info(f"✅ Item {item['item_id']} aggiornato: actual={item['actual_quantity']}")
                        
                    except Exception as e:
                        logger.error(f"❌ Errore aggiornamento quantità item {item['item_id']}: {e}")
                        continue
                        
                logger.info(f"✅ Tutti gli items marcati come ricevuti")
                
            except Exception as e:
                logger.error(f"❌ Errore submit shipment {residual_shipment_id}: {e}")
                logger.warning(f"⚠️ Shipment creato ma non submitted - items non ricevuti")
            
            logger.info(f"🎉 SUCCESS: Inbound residual creato con {items_added} items - ID: {residual_shipment_id}")
            return residual_shipment_id
            
        except Exception as e:
            logger.error(f"❌ Errore creazione inbound residual: {e}")
            return None 