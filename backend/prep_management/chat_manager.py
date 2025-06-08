"""
Sistema di gestione delle conversazioni bidirezionali Telegram.
Gestisce l'isolamento tra clienti diversi e le conversazioni attive per admin.
"""

import uuid
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from django.utils import timezone
from django.db.models import Q

from .models import (
    TelegramNotification, TelegramConversation, TelegramChatMessage, 
    AdminActiveConversation
)
from .services import TelegramService, ADMIN_EMAIL
from .translations import get_text

logger = logging.getLogger(__name__)


class ChatManager:
    """Gestisce le conversazioni bidirezionali tra clienti e admin."""
    
    def __init__(self):
        self.telegram_service = TelegramService()
    
    def handle_customer_message(self, chat_id: int, message_text: str) -> Dict:
        """
        Gestisce un messaggio in arrivo da un cliente.
        
        Args:
            chat_id: Chat ID del cliente
            message_text: Testo del messaggio
            
        Returns:
            Dict con risultato dell'operazione
        """
        try:
            # Trova l'utente dal chat_id
            sender = TelegramNotification.objects.get(
                chat_id=chat_id, 
                is_active=True
            )
            
            # Se è l'admin, gestisce diversamente
            if sender.email == ADMIN_EMAIL:
                return self.handle_admin_message(chat_id, message_text)
            
            # Ottieni o crea conversazione per questo cliente
            conversation = self.get_or_create_conversation(sender.email)
            
            # Salva il messaggio
            chat_message = TelegramChatMessage.objects.create(
                conversation=conversation,
                sender_chat_id=chat_id,
                sender_email=sender.email,
                message_type='customer_to_admin',
                message_text=message_text
            )
            
            # Aggiorna timestamp conversazione
            conversation.last_message_at = timezone.now()
            conversation.save()
            
            # Invia il messaggio al gruppo (stesso cliente + admin)
            recipients = self.get_conversation_recipients(sender.email)
            delivered_to = []
            
            # Filtra solo destinatari validi (esistenti e attivi)
            valid_recipients = []
            for recipient in recipients:
                if recipient.chat_id != chat_id:  # Non inviare a se stesso
                    # Verifica che il destinatario sia valido
                    if recipient.is_active:
                        valid_recipients.append(recipient)
                    else:
                        logger.warning(f"Destinatario non attivo: {recipient.email}")
            
            if not valid_recipients:
                logger.info(f"Nessun destinatario valido per {sender.email}, solo salvataggio messaggio")
                return {
                    'success': True,
                    'message': 'Messaggio salvato (nessun destinatario disponibile)',
                    'conversation_id': conversation.thread_id,
                    'delivered_to': 0
                }
            
            for recipient in valid_recipients:
                # Formatta messaggio diversamente per admin vs cliente
                if recipient.email == ADMIN_EMAIL:
                    formatted_message = self.format_message_for_admin(
                        sender.email, message_text, conversation
                    )
                    # Imposta questa come conversazione attiva per admin
                    self.set_admin_active_conversation(recipient.chat_id, conversation)
                else:
                    # Messaggio normale per altri utenti dello stesso cliente
                    formatted_message = f"💬 <b>{sender.get_full_name()}</b>:\n{message_text}"
                
                # Invia messaggio con gestione errori
                try:
                    success = self.telegram_service.send_message(
                        chat_id=recipient.chat_id,
                        text=formatted_message
                    )
                    
                    if success.get('ok'):
                        delivered_to.append(recipient.chat_id)
                    else:
                        logger.warning(f"Invio fallito a {recipient.chat_id}: {success}")
                        
                except Exception as e:
                    logger.error(f"Errore invio a {recipient.email} ({recipient.chat_id}): {str(e)}")
                    # Continua con gli altri destinatari
            
            # Aggiorna delivery status
            chat_message.delivered_to = delivered_to
            chat_message.save()
            
            logger.info(f"Messaggio cliente {sender.email} inviato a {len(delivered_to)} destinatari")
            
            return {
                'success': True,
                'message': 'Messaggio inviato al supporto',
                'conversation_id': conversation.thread_id,
                'delivered_to': len(delivered_to)
            }
            
        except TelegramNotification.DoesNotExist:
            logger.warning(f"Utente non registrato: chat_id {chat_id}")
            return {
                'success': False,
                'error': 'Utente non registrato'
            }
        except Exception as e:
            logger.error(f"Errore gestione messaggio cliente {chat_id}: {str(e)}")
            # Log traceback per debug
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                'success': False,
                'error': 'Errore del sistema'
            }
    
    def handle_admin_message(self, admin_chat_id: int, message_text: str) -> Dict:
        """
        Gestisce un messaggio dall'admin.
        
        Args:
            admin_chat_id: Chat ID dell'admin
            message_text: Testo del messaggio
            
        Returns:
            Dict con risultato dell'operazione
        """
        try:
            # Verifica che sia effettivamente admin
            admin_user = TelegramNotification.objects.get(
                chat_id=admin_chat_id,
                email=ADMIN_EMAIL,
                is_active=True
            )
            
            # Gestisce comandi speciali
            if message_text.startswith('/'):
                return self.handle_admin_command(admin_chat_id, message_text)
            
            # Gestisce reply con @ (es: @A il tuo messaggio)
            if message_text.startswith('@'):
                return self.handle_admin_reply_with_alias(admin_chat_id, message_text)
            
            # Messaggio normale - va alla conversazione attiva
            active_conv = self.get_admin_active_conversation(admin_chat_id)
            
            if not active_conv:
                # Nessuna conversazione attiva - chiedi quale scegliere
                return self.show_active_conversations(admin_chat_id)
            
            # Invia alla conversazione attiva
            return self.send_admin_message_to_conversation(
                admin_chat_id, active_conv, message_text
            )
            
        except TelegramNotification.DoesNotExist:
            logger.warning(f"Admin non trovato: chat_id {admin_chat_id}")
            return {
                'success': False,
                'error': 'Admin non autorizzato'
            }
        except Exception as e:
            logger.error(f"Errore gestione messaggio admin {admin_chat_id}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def handle_admin_command(self, admin_chat_id: int, command: str) -> Dict:
        """Gestisce i comandi admin."""
        
        parts = command.split(' ', 2)
        cmd = parts[0].lower()
        
        if cmd == '/list':
            return self.show_active_conversations(admin_chat_id)
        
        elif cmd == '/switch' and len(parts) >= 2:
            alias = parts[1].upper()
            return self.switch_admin_conversation(admin_chat_id, alias)
        
        elif cmd == '/broadcast' and len(parts) >= 2:
            message = ' '.join(parts[1:])
            return self.send_broadcast_message(admin_chat_id, message)
        
        elif cmd == '/close' and len(parts) >= 2:
            alias = parts[1].upper()
            return self.close_conversation(admin_chat_id, alias)
        
        else:
            help_text = """
🛠️ <b>Comandi Admin</b>

• <code>/list</code> - Mostra conversazioni attive
• <code>/switch [A]</code> - Cambia conversazione attiva
• <code>/broadcast [messaggio]</code> - Invia a tutti i clienti
• <code>/close [A]</code> - Chiudi conversazione
• <code>@A [messaggio]</code> - Rispondi al cliente A

💬 <b>Messaggi normali</b> vanno alla conversazione attiva.
            """
            self.telegram_service.send_message(admin_chat_id, help_text)
            return {'success': True, 'message': 'Help inviato'}
    
    def get_or_create_conversation(self, customer_email: str) -> TelegramConversation:
        """Ottiene o crea una conversazione per un cliente."""
        
        # Cerca conversazione attiva esistente
        conversation = TelegramConversation.objects.filter(
            customer_email=customer_email,
            is_active=True
        ).first()
        
        if not conversation:
            # Crea nuova conversazione
            thread_id = f"chat_{uuid.uuid4().hex[:8]}"
            conversation = TelegramConversation.objects.create(
                customer_email=customer_email,
                thread_id=thread_id,
                is_active=True
            )
            logger.info(f"Nuova conversazione creata: {thread_id} per {customer_email}")
        
        return conversation
    
    def get_conversation_recipients(self, customer_email: str) -> List[TelegramNotification]:
        """Ottiene tutti i destinatari per una conversazione (cliente + admin)."""
        
        return TelegramNotification.objects.filter(
            Q(email=customer_email) | Q(email=ADMIN_EMAIL),
            is_active=True
        )
    
    def format_message_for_admin(
        self, 
        customer_email: str, 
        message_text: str, 
        conversation: TelegramConversation
    ) -> str:
        """Formatta un messaggio per l'admin con contesto."""
        
        try:
            alias = conversation.get_customer_alias()
        except Exception:
            alias = 'X'
        
        # Limita lunghezza messaggio per evitare problemi
        display_message = message_text[:200] + "..." if len(message_text) > 200 else message_text
        
        formatted = f"""🔔 <b>Nuovo messaggio Cliente {alias}</b>
📧 {customer_email}

💬 "{display_message}"

📝 <i>Rispondi normalmente o usa @{alias}</i>"""
        
        return formatted
    
    def set_admin_active_conversation(
        self, 
        admin_chat_id: int, 
        conversation: TelegramConversation
    ):
        """Imposta la conversazione attiva per un admin."""
        
        active_conv, created = AdminActiveConversation.objects.get_or_create(
            admin_chat_id=admin_chat_id,
            defaults={'active_conversation': conversation}
        )
        
        if not created:
            active_conv.active_conversation = conversation
            active_conv.save()
        
        logger.info(f"Conversazione attiva per admin {admin_chat_id}: {conversation.thread_id}")
    
    def get_admin_active_conversation(self, admin_chat_id: int) -> Optional[TelegramConversation]:
        """Ottiene la conversazione attiva per un admin."""
        
        try:
            active_conv = AdminActiveConversation.objects.get(admin_chat_id=admin_chat_id)
            return active_conv.active_conversation
        except AdminActiveConversation.DoesNotExist:
            return None
    
    def show_active_conversations(self, admin_chat_id: int) -> Dict:
        """Mostra le conversazioni attive all'admin."""
        
        # Trova conversazioni con messaggi recenti (ultime 24h)
        recent_threshold = timezone.now() - timedelta(hours=24)
        
        conversations = TelegramConversation.objects.filter(
            is_active=True,
            last_message_at__gte=recent_threshold
        ).order_by('-last_message_at')
        
        if not conversations.exists():
            message = "📭 Nessuna conversazione attiva nelle ultime 24 ore"
            self.telegram_service.send_message(admin_chat_id, message)
            return {'success': True, 'message': 'Nessuna conversazione attiva'}
        
        # Formatta lista conversazioni
        conv_list = ["🗂️ <b>Conversazioni Attive</b>\n"]
        
        current_active = self.get_admin_active_conversation(admin_chat_id)
        
        for conv in conversations:
            alias = conv.get_customer_alias()
            status = "⭐" if conv == current_active else "💬"
            time_ago = self.get_time_ago(conv.last_message_at)
            
            conv_list.append(
                f"{status} <b>Cliente {alias}</b> ({conv.customer_email})\n"
                f"   🕒 {time_ago}\n"
                f"   🆔 {conv.thread_id}\n"
            )
        
        conv_list.append("\n📝 <i>Usa /switch [A] per cambiare conversazione attiva</i>")
        
        message = "\n".join(conv_list)
        self.telegram_service.send_message(admin_chat_id, message)
        
        return {'success': True, 'conversations': len(conversations)}
    
    def send_admin_message_to_conversation(
        self, 
        admin_chat_id: int, 
        conversation: TelegramConversation, 
        message_text: str
    ) -> Dict:
        """Invia un messaggio dell'admin a una conversazione specifica."""
        
        try:
            # Salva il messaggio
            chat_message = TelegramChatMessage.objects.create(
                conversation=conversation,
                sender_chat_id=admin_chat_id,
                sender_email=ADMIN_EMAIL,
                message_type='admin_to_customer',
                message_text=message_text
            )
            
            # Aggiorna timestamp conversazione
            conversation.last_message_at = timezone.now()
            conversation.save()
            
            # Trova tutti i clienti di questa conversazione
            customer_users = TelegramNotification.objects.filter(
                email=conversation.customer_email,
                is_active=True
            )
            
            delivered_to = []
            
            for user in customer_users:
                # Formatta messaggio per il cliente
                formatted_message = f"💬 <b>Supporto</b>:\n{message_text}"
                
                success = self.telegram_service.send_message(
                    chat_id=user.chat_id,
                    text=formatted_message
                )
                
                if success.get('ok'):
                    delivered_to.append(user.chat_id)
            
            # Aggiorna delivery status
            chat_message.delivered_to = delivered_to
            chat_message.save()
            
            # Conferma all'admin
            alias = conversation.get_customer_alias()
            confirm_message = f"✅ Messaggio inviato a Cliente {alias} ({len(delivered_to)} destinatari)"
            self.telegram_service.send_message(admin_chat_id, confirm_message)
            
            logger.info(f"Messaggio admin inviato a conversazione {conversation.thread_id}")
            
            return {
                'success': True,
                'conversation_id': conversation.thread_id,
                'delivered_to': len(delivered_to)
            }
            
        except Exception as e:
            logger.error(f"Errore invio messaggio admin: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def get_time_ago(self, timestamp: datetime) -> str:
        """Calcola quanto tempo fa è avvenuto un evento."""
        
        now = timezone.now()
        diff = now - timestamp
        
        if diff.seconds < 3600:  # Meno di 1 ora
            minutes = diff.seconds // 60
            return f"{minutes} minuti fa"
        elif diff.days == 0:  # Oggi
            hours = diff.seconds // 3600
            return f"{hours} ore fa"
        elif diff.days == 1:
            return "Ieri"
        else:
            return f"{diff.days} giorni fa"
    
    def handle_admin_reply_with_alias(self, admin_chat_id: int, message_text: str) -> Dict:
        """Gestisce le risposte admin con alias (@A messaggio)."""
        
        try:
            # Estrai alias e messaggio (@A il tuo messaggio)
            parts = message_text.split(' ', 1)
            if len(parts) < 2:
                error_msg = "❌ Formato non valido. Usa: @A il tuo messaggio"
                self.telegram_service.send_message(admin_chat_id, error_msg)
                return {'success': False, 'error': 'Formato non valido'}
            
            alias = parts[0][1:].upper()  # Rimuovi @ e converti in maiuscolo
            reply_message = parts[1]
            
            # Trova conversazione per alias
            conversation = self.get_conversation_by_alias(alias)
            
            if not conversation:
                error_msg = f"❌ Cliente {alias} non trovato o conversazione non attiva"
                self.telegram_service.send_message(admin_chat_id, error_msg)
                return {'success': False, 'error': 'Conversazione non trovata'}
            
            # Invia messaggio alla conversazione
            return self.send_admin_message_to_conversation(
                admin_chat_id, conversation, reply_message
            )
            
        except Exception as e:
            logger.error(f"Errore reply con alias: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def get_conversation_by_alias(self, alias: str) -> Optional[TelegramConversation]:
        """Trova una conversazione attiva per alias."""
        
        try:
            # Per ora, usa un mapping semplice basato sull'ordine di creazione
            conversations = TelegramConversation.objects.filter(
                is_active=True
            ).order_by('created_at')
            
            # Converte l'alias in indice (A=0, B=1, etc.)
            index = ord(alias.upper()) - 65  # A=0, B=1, C=2, etc.
            if 0 <= index < conversations.count():
                return conversations[index]
            
        except (ValueError, IndexError, AttributeError):
            logger.warning(f"Errore nel trovare conversazione per alias {alias}")
        
        return None
    
    def switch_admin_conversation(self, admin_chat_id: int, alias: str) -> Dict:
        """Cambia la conversazione attiva dell'admin."""
        
        conversation = self.get_conversation_by_alias(alias)
        
        if not conversation:
            error_msg = f"❌ Cliente {alias} non trovato"
            self.telegram_service.send_message(admin_chat_id, error_msg)
            return {'success': False, 'error': 'Conversazione non trovata'}
        
        # Imposta come conversazione attiva
        self.set_admin_active_conversation(admin_chat_id, conversation)
        
        # Conferma
        confirm_msg = f"✅ Conversazione attiva cambiata a Cliente {alias} ({conversation.customer_email})"
        self.telegram_service.send_message(admin_chat_id, confirm_msg)
        
        return {'success': True, 'conversation_id': conversation.thread_id}
    
    def send_broadcast_message(self, admin_chat_id: int, message_text: str) -> Dict:
        """Invia un messaggio broadcast a tutti i clienti attivi."""
        
        try:
            # Trova tutti i clienti registrati (escluso admin)
            customers = TelegramNotification.objects.filter(
                is_active=True
            ).exclude(email=ADMIN_EMAIL)
            
            if not customers.exists():
                error_msg = "❌ Nessun cliente registrato per il broadcast"
                self.telegram_service.send_message(admin_chat_id, error_msg)
                return {'success': False, 'error': 'Nessun cliente'}
            
            delivered_to = []
            
            for customer in customers:
                # Formatta messaggio broadcast
                formatted_message = f"📢 <b>Messaggio dal supporto</b>:\n{message_text}"
                
                success = self.telegram_service.send_message(
                    chat_id=customer.chat_id,
                    text=formatted_message
                )
                
                if success.get('ok'):
                    delivered_to.append(customer.chat_id)
            
            # Conferma all'admin
            confirm_msg = f"📢 Broadcast inviato a {len(delivered_to)} clienti"
            self.telegram_service.send_message(admin_chat_id, confirm_msg)
            
            logger.info(f"Broadcast inviato a {len(delivered_to)} clienti")
            
            return {
                'success': True,
                'delivered_to': len(delivered_to),
                'total_customers': customers.count()
            }
            
        except Exception as e:
            logger.error(f"Errore broadcast: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def close_conversation(self, admin_chat_id: int, alias: str) -> Dict:
        """Chiude una conversazione."""
        
        conversation = self.get_conversation_by_alias(alias)
        
        if not conversation:
            error_msg = f"❌ Cliente {alias} non trovato"
            self.telegram_service.send_message(admin_chat_id, error_msg)
            return {'success': False, 'error': 'Conversazione non trovata'}
        
        # Chiudi conversazione
        conversation.is_active = False
        conversation.save()
        
        # Rimuovi da conversazioni attive se era quella corrente
        try:
            active_conv = AdminActiveConversation.objects.get(admin_chat_id=admin_chat_id)
            if active_conv.active_conversation == conversation:
                active_conv.active_conversation = None
                active_conv.save()
        except AdminActiveConversation.DoesNotExist:
            pass
        
        # Conferma
        confirm_msg = f"✅ Conversazione con Cliente {alias} chiusa"
        self.telegram_service.send_message(admin_chat_id, confirm_msg)
        
        return {'success': True, 'conversation_id': conversation.thread_id} 