"""
Comando per testare il sistema di messaggistica bidirezionale.
"""

from django.core.management.base import BaseCommand
from prep_management.utils.messaging import (
    MessageSession, 
    send_outbound_without_inbound_notification,
    send_box_services_request,
    cleanup_old_messages
)
from prep_management.models import OutgoingMessage, IncomingMessage
import time


class Command(BaseCommand):
    help = 'Testa il sistema di messaggistica bidirezionale'

    def add_arguments(self, parser):
        parser.add_argument(
            '--action',
            type=str,
            choices=['send', 'wait', 'send_and_wait', 'cleanup', 'status'],
            default='status',
            help='Azione da eseguire'
        )
        parser.add_argument(
            '--session-id',
            type=str,
            help='ID della sessione per il test'
        )
        parser.add_argument(
            '--timeout',
            type=int,
            default=10,
            help='Timeout in secondi per l\'attesa'
        )

    def handle(self, *args, **options):
        action = options['action']
        session_id = options['session_id']
        timeout = options['timeout']

        if action == 'status':
            self.show_status()
        
        elif action == 'send':
            self.test_send(session_id)
        
        elif action == 'wait':
            if not session_id:
                self.stdout.write(self.style.ERROR('--session-id richiesto per wait'))
                return
            self.test_wait(session_id, timeout)
        
        elif action == 'send_and_wait':
            self.test_send_and_wait(session_id, timeout)
        
        elif action == 'cleanup':
            self.test_cleanup()

    def show_status(self):
        """Mostra lo stato attuale dei messaggi."""
        outgoing_total = OutgoingMessage.objects.count()
        outgoing_consumed = OutgoingMessage.objects.filter(consumed=True).count()
        outgoing_pending = outgoing_total - outgoing_consumed
        
        incoming_total = IncomingMessage.objects.count()
        incoming_processed = IncomingMessage.objects.filter(processed=True).count()
        incoming_pending = incoming_total - incoming_processed
        
        self.stdout.write(self.style.SUCCESS('=== STATO MESSAGGISTICA ==='))
        self.stdout.write(f'Messaggi in uscita: {outgoing_total} totali, {outgoing_consumed} consumati, {outgoing_pending} in attesa')
        self.stdout.write(f'Messaggi in entrata: {incoming_total} totali, {incoming_processed} processati, {incoming_pending} in attesa')
        
        if outgoing_pending > 0:
            self.stdout.write('\nMessaggi in uscita in attesa:')
            for msg in OutgoingMessage.objects.filter(consumed=False)[:5]:
                self.stdout.write(f'  - {msg.message_id} (ID: {msg.id}, creato: {msg.created_at})')
        
        if incoming_pending > 0:
            self.stdout.write('\nMessaggi in entrata in attesa:')
            for msg in IncomingMessage.objects.filter(processed=False)[:5]:
                self.stdout.write(f'  - {msg.message_type} (session: {msg.session_id}, creato: {msg.created_at})')

    def test_send(self, session_id):
        """Testa l'invio di un messaggio."""
        self.stdout.write('Invio messaggio di test...')
        
        sent_msg, _ = send_outbound_without_inbound_notification(
            merchant_name='Test Merchant',
            outbound_shipment_name='Test Shipment',
            wait_for_response=False
        )
        
        self.stdout.write(self.style.SUCCESS(f'Messaggio inviato: ID {sent_msg.id}, session {sent_msg.parameters.get("session_id")}'))

    def test_wait(self, session_id, timeout):
        """Testa l'attesa di una risposta."""
        self.stdout.write(f'Attendo risposta per sessione {session_id} (timeout: {timeout}s)...')
        
        session = MessageSession(session_id)
        messages = session.wait_for_response(timeout)
        
        if messages:
            self.stdout.write(self.style.SUCCESS(f'Ricevuti {len(messages)} messaggi:'))
            for msg in messages:
                self.stdout.write(f'  - {msg.message_type}: {msg.payload}')
        else:
            self.stdout.write(self.style.WARNING('Nessun messaggio ricevuto (timeout)'))

    def test_send_and_wait(self, session_id, timeout):
        """Testa invio e attesa di risposta."""
        self.stdout.write(f'Invio messaggio e attendo risposta (timeout: {timeout}s)...')
        
        sent_msg, received_msgs = send_outbound_without_inbound_notification(
            merchant_name='Test Merchant',
            outbound_shipment_name='Test Shipment',
            wait_for_response=True,
            timeout=timeout
        )
        
        session_id = sent_msg.parameters.get('session_id')
        self.stdout.write(f'Messaggio inviato: session {session_id}')
        
        if received_msgs:
            self.stdout.write(self.style.SUCCESS(f'Ricevuti {len(received_msgs)} messaggi:'))
            for msg in received_msgs:
                self.stdout.write(f'  - {msg.message_type}: {msg.payload}')
        else:
            self.stdout.write(self.style.WARNING('Nessuna risposta ricevuta (timeout)'))
            self.stdout.write(f'Per testare manualmente, invia un POST a:')
            self.stdout.write(f'/prep_management/queue/receive/')
            self.stdout.write(f'con payload: {{"session_id": "{session_id}", "message_type": "USER_RESPONSE", "payload": {{"action": "test_response"}}}}')

    def test_cleanup(self):
        """Testa la pulizia dei messaggi vecchi."""
        self.stdout.write('Pulizia messaggi vecchi...')
        
        deleted_count = cleanup_old_messages(hours=0)  # Elimina tutto per test
        
        self.stdout.write(self.style.SUCCESS(f'Eliminati {deleted_count} messaggi vecchi')) 