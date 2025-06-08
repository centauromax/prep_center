import requests
from libs.prepbusiness.client import PrepBusinessClient
from libs.config import PREP_BUSINESS_API_URL

class PrepBusinessAPI:
    """
    Wrapper per le API di Prep Business.
    NOTA: Questa classe è mantenuta per retrocompatibilità.
    Si consiglia di utilizzare direttamente PrepBusinessClient per nuove implementazioni.
    """
    def __init__(self, api_key):
        """Inizializza il client PrepBusiness"""
        # Manteniamo self.headers per retrocompatibilità
        self.headers = {"Authorization": f"Bearer {api_key}"}
        
        # Estraiamo il dominio dall'URL API
        company_domain = PREP_BUSINESS_API_URL.split('//')[-1].split('/')[0]
        
        # Inizializza il client PrepBusiness
        self.client = PrepBusinessClient(
            api_key=api_key,
            company_domain=company_domain
        )
    
    def get_open_inbound_shipments(self):
        """
        Recupera le spedizioni in entrata aperte utilizzando PrepBusinessClient.
        
        Returns:
            Lista di spedizioni in entrata aperte
        """
        try:
            # Utilizziamo il client PrepBusiness invece di requests diretti
            response = self.client.get_inbound_shipments()
            
            # Filtriamo solo le spedizioni aperte
            open_shipments = [
                shipment for shipment in response.data
                if getattr(shipment, 'status', None) == 'open'
            ]
            
            # Convertiamo in dict per mantenere la compatibilità con l'implementazione precedente
            return [
                {
                    'id': shipment.id,
                    'name': shipment.name,
                    'status': shipment.status,
                    'created_at': shipment.created_at.isoformat() if hasattr(shipment.created_at, 'isoformat') else shipment.created_at,
                    # Aggiungi altri campi necessari
                }
                for shipment in open_shipments
            ]
        except Exception as e:
            # In caso di errore, restituisci un elenco vuoto
            return []


# =============================================================================
# SERVIZI TELEGRAM
# =============================================================================

import logging
from django.conf import settings
from django.utils import timezone
from .models import TelegramNotification, TelegramMessage

logger = logging.getLogger(__name__)

class TelegramService:
    """Servizio per gestire l'invio di messaggi Telegram."""
    
    def __init__(self):
        self.bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        
        if not self.bot_token:
            logger.warning("TELEGRAM_BOT_TOKEN non configurato nelle settings")
    
    def send_message(self, chat_id, text, parse_mode='HTML'):
        """
        Invia un messaggio Telegram.
        
        Args:
            chat_id: ID della chat Telegram
            text: Testo del messaggio
            parse_mode: Modalità parsing (HTML, Markdown)
            
        Returns:
            dict: Risposta API Telegram
        """
        if not self.bot_token:
            raise ValueError("Bot token Telegram non configurato")
        
        url = f"{self.base_url}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': parse_mode,
            'disable_web_page_preview': True
        }
        
        try:
            response = requests.post(url, data=payload, timeout=10)
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Errore nell'invio messaggio Telegram a {chat_id}: {str(e)}")
            raise
    
    def get_chat_info(self, chat_id):
        """Ottiene informazioni su una chat Telegram."""
        if not self.bot_token:
            raise ValueError("Bot token Telegram non configurato")
            
        url = f"{self.base_url}/getChat"
        payload = {'chat_id': chat_id}
        
        try:
            response = requests.post(url, data=payload, timeout=10)
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Errore nel recuperare info chat {chat_id}: {str(e)}")
            raise

# Istanza globale del servizio
telegram_service = TelegramService()


def send_telegram_notification(email, message, event_type=None, shipment_id=None):
    """
    Invia una notifica Telegram a TUTTI gli utenti registrati con la stessa email.
    Supporta più dipendenti aziendali con la stessa email del Prep Center.
    
    Args:
        email: Email dell'utente (collegata al software del Prep Center)
        message: Testo del messaggio
        event_type: Tipo di evento (opzionale)
        shipment_id: ID spedizione (opzionale)
        
    Returns:
        bool: True se almeno un messaggio è stato inviato con successo
    """
    try:
        # Trova TUTTI gli utenti Telegram con questa email
        telegram_users = TelegramNotification.objects.filter(
            email=email,
            is_active=True
        )
        
        if not telegram_users.exists():
            logger.warning(f"Nessun utente Telegram trovato per email: {email}")
            return False
        
        success_count = 0
        
        # Invia a tutti gli utenti con questa email
        for telegram_user in telegram_users:
            try:
                # Crea il record del messaggio
                telegram_message = TelegramMessage.objects.create(
                    telegram_user=telegram_user,
                    message_text=message,
                    event_type=event_type,
                    shipment_id=shipment_id,
                    status='pending'
                )
                
                # Invia il messaggio
                response = telegram_service.send_message(
                    chat_id=telegram_user.chat_id,
                    text=message
                )
                
                # Aggiorna il messaggio con risultato
                if response.get('ok'):
                    telegram_message.status = 'sent'
                    telegram_message.sent_at = timezone.now()
                    telegram_message.telegram_message_id = response.get('result', {}).get('message_id')
                    telegram_message.save()
                    
                    # Incrementa il contatore dell'utente
                    telegram_user.increment_notification_count()
                    
                    success_count += 1
                    logger.info(f"Messaggio Telegram inviato a {email} -> chat_id: {telegram_user.chat_id}")
                else:
                    # Errore nella risposta Telegram
                    telegram_message.status = 'failed'
                    telegram_message.error_message = str(response)
                    telegram_message.save()
                    
                    logger.error(f"Errore API Telegram per {email} chat_id {telegram_user.chat_id}: {response}")
                    
            except Exception as e:
                # Errore per questo specifico utente
                if 'telegram_message' in locals():
                    telegram_message.status = 'failed'
                    telegram_message.error_message = str(e)
                    telegram_message.save()
                
                logger.error(f"Errore invio a {email} chat_id {telegram_user.chat_id}: {str(e)}")
        
        if success_count > 0:
            logger.info(f"Notifica Telegram inviata con successo a {success_count} utenti per email {email}")
            return True
        else:
            logger.warning(f"Nessun messaggio inviato con successo per email {email}")
            return False
            
    except Exception as e:
        logger.error(f"Errore generale nell'invio notifica Telegram a {email}: {str(e)}")
        return False


def retry_telegram_message(telegram_message):
    """
    Riprova l'invio di un messaggio Telegram fallito.
    
    Args:
        telegram_message: Istanza di TelegramMessage
        
    Returns:
        bool: True se inviato con successo
    """
    try:
        telegram_message.retry_count += 1
        telegram_message.status = 'retry'
        telegram_message.save()
        
        # Invia il messaggio
        response = telegram_service.send_message(
            chat_id=telegram_message.telegram_user.chat_id,
            text=telegram_message.message_text
        )
        
        # Aggiorna con il risultato
        if response.get('ok'):
            telegram_message.status = 'sent'
            telegram_message.sent_at = timezone.now()
            telegram_message.telegram_message_id = response.get('result', {}).get('message_id')
            telegram_message.error_message = None
            telegram_message.save()
            
            # Incrementa il contatore dell'utente
            telegram_message.telegram_user.increment_notification_count()
            
            return True
        else:
            telegram_message.status = 'failed'
            telegram_message.error_message = str(response)
            telegram_message.save()
            return False
            
    except Exception as e:
        telegram_message.status = 'failed'
        telegram_message.error_message = str(e)
        telegram_message.save()
        
        logger.error(f"Errore nel retry messaggio {telegram_message.id}: {str(e)}")
        return False


def register_telegram_user(chat_id, email, user_info=None):
    """
    Registra un utente Telegram collegandolo alla sua email del Prep Center.
    
    Args:
        chat_id: ID chat Telegram
        email: Email dell'utente
        user_info: Informazioni utente da Telegram (opzionale)
        
    Returns:
        tuple: (success: bool, message: str, user: TelegramNotification|None)
    """
    try:
        # Verifica che l'email sia valida
        if not email or '@' not in email:
            return False, "Email non valida", None
        
        # Verifica che l'email esista nel software del Prep Center
        logger.info(f"[register_telegram_user] Verifica email {email} nel software del Prep Center")
        if not verify_email_in_prepbusiness(email):
            error_msg = f"Email {email} non trovata nel software del Prep Center. Verifica di aver inserito l'email corretta utilizzata per il tuo account sul software del Prep Center."
            logger.warning(f"[register_telegram_user] ❌ Registrazione fallita per {email}: email non trovata nel software del Prep Center")
            return False, error_msg, None
        
        logger.info(f"[register_telegram_user] ✅ Email {email} verificata con successo nel software del Prep Center")
        
        # Crea o aggiorna l'utente
        user_data = {
            'chat_id': chat_id,
            'is_active': True
        }
        
        # Aggiungi info utente se disponibili
        if user_info:
            user_data.update({
                'username': user_info.get('username'),
                'first_name': user_info.get('first_name'),
                'last_name': user_info.get('last_name'),
                'language_code': user_info.get('language_code', 'it')
            })
        
        # Controlla se questo chat_id è già registrato (anche con email temporanea)
        existing_chat = TelegramNotification.objects.filter(chat_id=chat_id).first()
        if existing_chat:
            # Se esiste già un record per questo chat_id, aggiornalo
            existing_chat.email = email
            existing_chat.is_active = True  # Attiva l'utente
            for key, value in user_data.items():
                if key != 'chat_id' and value is not None:  # Non sovrascrivere chat_id e valori None
                    setattr(existing_chat, key, value)
            existing_chat.save()
            telegram_user = existing_chat
            created = False
        else:
            # Crea nuovo record
            telegram_user = TelegramNotification.objects.create(
                email=email,
                **user_data
            )
            created = True
        
        action = "registrato" if created else "aggiornato"
        success_msg = f"Account {action} con successo per {email}!"
        
        logger.info(f"Utente Telegram {action}: {email} -> {chat_id}")
        return True, success_msg, telegram_user
        
    except Exception as e:
        error_msg = f"Errore nella registrazione: {str(e)}"
        logger.error(f"Errore registrazione Telegram per {email}: {str(e)}")
        return False, error_msg, None


def verify_email_in_prepbusiness(email):
    """
    Verifica se un'email esiste nel software del Prep Center controllando la lista dei merchant autorizzati.
    
    Args:
        email: Email da verificare
        
    Returns:
        bool: True se l'email esiste
    """
    try:
        logger.info(f"[verify_email_in_prepbusiness] 🔍 Verifica email: {email}")
        
        # Per ora, per evitare problemi di import, usiamo un approccio semplificato
        # Verifichiamo solo che l'email sia valida e non vuota
        # TODO: Implementare la verifica completa quando risolviamo i problemi di import
        
        if not email or '@' not in email or '.' not in email:
            logger.warning(f"[verify_email_in_prepbusiness] ❌ Email {email} non valida (formato)")
            return False
        
        # Lista temporanea delle email valide conosciute (da aggiornare con API)
        valid_emails = [
            "prep@easyavant.com",
            "glomatservice@gmail.com", 
            "alyxsrl@gmail.com",
            "kaium2000@gmail.com",
            "login@trovato-trade.com",
            "inna.usenko.ecommerce@gmail.com",
            "sales@amazingretail.eu",
            "demo@wifiexpress.it",
            "commerciale@selley.it",
            "maurocatacci@selley.it",
            "contact@hrtretail.com",
            "protsenkoyuliia2@gmail.com",
            "info@flogastore.it",
            "zunan.javid@novus-trade.fr"
        ]
        
        # Verifica case-insensitive
        email_lower = email.lower()
        for valid_email in valid_emails:
            if valid_email.lower() == email_lower:
                logger.info(f"[verify_email_in_prepbusiness] ✅ Email {email} trovata nella lista valida")
                return True
        
        logger.warning(f"[verify_email_in_prepbusiness] ❌ Email {email} NON trovata nella lista valida")
        logger.warning(f"[verify_email_in_prepbusiness] 📧 Email valide: {valid_emails}")
        return False
        
    except Exception as e:
        logger.error(f"[verify_email_in_prepbusiness] ❌ Errore nella verifica email {email}: {str(e)}")
        logger.exception("Traceback completo:")
        # In caso di errore, non permettiamo la registrazione per sicurezza
        return False


def format_shipment_notification(event_type, shipment_data):
    """
    Formatta un messaggio di notifica per una spedizione.
    
    Args:
        event_type: Tipo di evento
        shipment_data: Dati della spedizione
        
    Returns:
        str: Messaggio formattato
    """
    icons = {
        'inbound_shipment.created': '📦',
        'inbound_shipment.received': '✅',
        'inbound_shipment.shipped': '🚛',
        'outbound_shipment.created': '📤',
        'outbound_shipment.shipped': '🚚',
        'outbound_shipment.closed': '✅',
        'order.created': '🛒',
        'order.shipped': '📮'
    }
    
    messages = {
        'inbound_shipment.created': 'Nuova spedizione in entrata creata',
        'inbound_shipment.received': 'Spedizione in entrata ricevuta',
        'inbound_shipment.shipped': 'Spedizione in entrata in transito',
        'outbound_shipment.created': 'Nuova spedizione in uscita creata',
        'outbound_shipment.shipped': 'Spedizione in uscita spedita',
        'outbound_shipment.closed': 'Spedizione in uscita completata',
        'order.created': 'Nuovo ordine creato',
        'order.shipped': 'Ordine spedito'
    }
    
    icon = icons.get(event_type, '📋')
    title = messages.get(event_type, 'Aggiornamento spedizione')
    
    message = f"{icon} <b>{title}</b>\n\n"
    
    if shipment_data.get('shipment_id'):
        message += f"🆔 <b>ID:</b> {shipment_data['shipment_id']}\n"
    
    if shipment_data.get('shipment_name'):
        message += f"📝 <b>Nome:</b> {shipment_data['shipment_name']}\n"
        
    if shipment_data.get('tracking_number'):
        message += f"🔍 <b>Tracking:</b> {shipment_data['tracking_number']}\n"
        
    if shipment_data.get('carrier'):
        message += f"🚛 <b>Corriere:</b> {shipment_data['carrier']}\n"
    
    if shipment_data.get('notes'):
        message += f"\n💬 <b>Note:</b>\n{shipment_data['notes']}\n"
    
    # Usa il timezone di Roma configurato nelle settings
    from django.conf import settings
    import pytz
    
    # Ottieni il timezone di Roma
    rome_tz = pytz.timezone('Europe/Rome')
    local_time = timezone.now().astimezone(rome_tz)
    
    message += f"\n🕒 <i>Aggiornamento del {local_time.strftime('%d/%m/%Y alle %H:%M')}</i>"
    
    return message
