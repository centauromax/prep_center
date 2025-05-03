import os
import time
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from libs.prepbusiness.client import PrepBusinessClient
from libs.config import (
    PREP_BUSINESS_API_URL,
    PREP_BUSINESS_API_KEY,
    PREP_BUSINESS_API_TIMEOUT,
)

class Command(BaseCommand):
    help = 'Configura un webhook su Prep Business per ricevere notifiche di stato spedizioni'

    def add_arguments(self, parser):
        parser.add_argument('--url', type=str, help='URL del webhook (es. https://tuodominio.com/prep_management/webhook/)')
        parser.add_argument('--merchant', type=int, help='ID del merchant per configurare un webhook specifico')
        parser.add_argument('--list', action='store_true', help='Elenca i webhook configurati')
        parser.add_argument('--delete', type=int, help='ID del webhook da eliminare')
        parser.add_argument('--test', action='store_true', help='Testa il webhook inviando un evento di prova')
        parser.add_argument('--webhook-id', type=int, help='ID del webhook da testare')

    def handle(self, *args, **options):
        try:
            # Estrai dominio dall'URL API
            api_url = PREP_BUSINESS_API_URL
            if not api_url:
                self.stderr.write(self.style.ERROR('PREP_BUSINESS_API_URL non configurato'))
                return
                
            domain = api_url.replace('https://', '').replace('http://', '').split('/')[0]
            
            # Crea cliente Prep Business
            client = PrepBusinessClient(
                api_key=PREP_BUSINESS_API_KEY,
                company_domain=domain,
                timeout=PREP_BUSINESS_API_TIMEOUT,
            )
            
            # Lista webhook
            if options['list']:
                self.list_webhooks(client, options['merchant'])
                return
                
            # Elimina webhook
            if options['delete']:
                self.delete_webhook(client, options['delete'], options['merchant'])
                return
                
            # Testa webhook
            if options['test']:
                webhook_id = options['webhook_id']
                if not webhook_id:
                    # Usa il primo webhook disponibile se non specificato
                    webhooks = client.get_webhooks().webhooks
                    if not webhooks:
                        self.stderr.write(self.style.ERROR('Nessun webhook trovato da testare. Creane uno prima.'))
                        return
                    webhook_id = webhooks[0].id
                    
                self.test_webhook(client, webhook_id, options['merchant'])
                return
                
            # Configura webhook
            webhook_url = options['url']
            if not webhook_url:
                # Usa un URL di default basato sulle impostazioni di Django
                # Per Railway, usa le variabili d'ambiente specifiche
                site_url = os.environ.get('RAILWAY_STATIC_URL') or os.environ.get('RAILWAY_PUBLIC_DOMAIN')
                
                if not site_url:
                    site_url = os.environ.get('SITE_URL', 'http://localhost:8000')
                else:
                    # Assicurati che l'URL inizi con https:// su Railway
                    site_url = f"https://{site_url}" if not site_url.startswith('http') else site_url
                    
                webhook_url = f"{site_url.rstrip('/')}/prep_management/webhook/"
                self.stdout.write(f"URL non specificato, uso: {webhook_url}")
                
            self.create_or_update_webhook(client, webhook_url, options['merchant'])
            
            # Se siamo su Railway, suggerisci di testare il webhook
            if os.environ.get('RAILWAY_STATIC_URL') or os.environ.get('RAILWAY_PUBLIC_DOMAIN'):
                self.stdout.write(self.style.WARNING(
                    "\nEsegui il test del webhook per verificare che funzioni correttamente:"
                    "\npython manage.py setup_webhook --test"
                ))
                
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Errore durante la configurazione del webhook: {str(e)}'))
            
    def list_webhooks(self, client, merchant_id=None):
        """Elenca i webhook configurati."""
        try:
            if merchant_id:
                response = client.get_merchant_webhooks(merchant_id=merchant_id)
                self.stdout.write(self.style.SUCCESS(f'Webhook configurati per il merchant {merchant_id}:'))
            else:
                response = client.get_webhooks()
                self.stdout.write(self.style.SUCCESS('Webhook globali configurati:'))
                
            webhooks = response.webhooks
            
            if not webhooks:
                self.stdout.write('Nessun webhook configurato')
                return
                
            for webhook in webhooks:
                self.stdout.write('-' * 50)
                self.stdout.write(f'ID: {webhook.id}')
                self.stdout.write(f'URL: {webhook.url}')
                self.stdout.write('Eventi configurati:')
                
                # Controlla quali eventi sono attivi
                for field, value in webhook.__dict__.items():
                    if field.startswith('receives_') and value:
                        event_name = field.replace('receives_', '')
                        self.stdout.write(f'  - {event_name}')
                        
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Errore durante il recupero dei webhook: {str(e)}'))
            
    def delete_webhook(self, client, webhook_id, merchant_id=None):
        """Elimina un webhook configurato."""
        try:
            if merchant_id:
                response = client.delete_merchant_webhook(merchant_id=merchant_id, webhook_id=webhook_id)
                self.stdout.write(self.style.SUCCESS(f'Webhook {webhook_id} eliminato per il merchant {merchant_id}'))
            else:
                response = client.delete_webhook(webhook_id=webhook_id)
                self.stdout.write(self.style.SUCCESS(f'Webhook globale {webhook_id} eliminato'))
                
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Errore durante l\'eliminazione del webhook: {str(e)}'))
            
    def create_or_update_webhook(self, client, webhook_url, merchant_id=None):
        """Crea o aggiorna un webhook."""
        try:
            # Controlla se esiste già un webhook con questo URL
            existing_webhook = None
            
            # Recupera i webhook esistenti
            if merchant_id:
                response = client.get_merchant_webhooks(merchant_id=merchant_id)
                webhooks = response.webhooks
            else:
                response = client.get_webhooks()
                webhooks = response.webhooks
                
            # Cerca un webhook con lo stesso URL
            for webhook in webhooks:
                if webhook.url == webhook_url:
                    existing_webhook = webhook
                    break
                    
            # Configura tutti gli eventi disponibili
            if existing_webhook:
                # Aggiorna il webhook esistente
                if merchant_id:
                    response = client.update_merchant_webhook(
                        merchant_id=merchant_id,
                        webhook_id=existing_webhook.id,
                        url=webhook_url,
                        invoice_created=True,
                        inbound_shipment_notes_updated=True,
                        inbound_shipment_created=True,
                        inbound_shipment_shipped=True,
                        inbound_shipment_received=True,
                        outbound_shipment_notes_updated=True,
                        outbound_shipment_created=True,
                        outbound_shipment_shipped=True,
                        outbound_shipment_closed=True,
                        order_shipped=True
                    )
                    self.stdout.write(self.style.SUCCESS(
                        f'Webhook aggiornato per il merchant {merchant_id}: {webhook_url}'))
                else:
                    response = client.update_webhook(
                        webhook_id=existing_webhook.id,
                        url=webhook_url,
                        invoice_created=True,
                        inbound_shipment_notes_updated=True,
                        inbound_shipment_created=True,
                        inbound_shipment_shipped=True,
                        inbound_shipment_received=True,
                        outbound_shipment_notes_updated=True,
                        outbound_shipment_created=True,
                        outbound_shipment_shipped=True,
                        outbound_shipment_closed=True,
                        order_shipped=True
                    )
                    self.stdout.write(self.style.SUCCESS(
                        f'Webhook globale aggiornato: {webhook_url}'))
            else:
                # Crea un nuovo webhook
                if merchant_id:
                    response = client.create_merchant_webhook(
                        merchant_id=merchant_id,
                        url=webhook_url,
                        invoice_created=True,
                        inbound_shipment_notes_updated=True,
                        inbound_shipment_created=True,
                        inbound_shipment_shipped=True,
                        inbound_shipment_received=True,
                        outbound_shipment_notes_updated=True,
                        outbound_shipment_created=True,
                        outbound_shipment_shipped=True,
                        outbound_shipment_closed=True,
                        order_shipped=True
                    )
                    self.stdout.write(self.style.SUCCESS(
                        f'Nuovo webhook creato per il merchant {merchant_id}: {webhook_url}'))
                else:
                    response = client.create_webhook(
                        url=webhook_url,
                        invoice_created=True,
                        inbound_shipment_notes_updated=True,
                        inbound_shipment_created=True,
                        inbound_shipment_shipped=True,
                        inbound_shipment_received=True,
                        outbound_shipment_notes_updated=True,
                        outbound_shipment_created=True,
                        outbound_shipment_shipped=True,
                        outbound_shipment_closed=True,
                        order_shipped=True
                    )
                    self.stdout.write(self.style.SUCCESS(
                        f'Nuovo webhook globale creato: {webhook_url}'))
                
            # Dettagli webhook
            webhook = response.webhook
            self.stdout.write('-' * 50)
            self.stdout.write('Dettagli webhook:')
            self.stdout.write(f'ID: {webhook.id}')
            self.stdout.write(f'URL: {webhook.url}')
            self.stdout.write('Eventi configurati:')
            
            # Mostra gli eventi attivi
            for field, value in webhook.__dict__.items():
                if field.startswith('receives_') and value:
                    event_name = field.replace('receives_', '')
                    self.stdout.write(f'  - {event_name}')
            
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Errore durante la creazione/aggiornamento del webhook: {str(e)}'))
            
    def test_webhook(self, client, webhook_id, merchant_id=None):
        """Testa un webhook inviando un evento di prova."""
        try:
            # Per ora, non c'è un metodo specifico per testare un webhook nell'API Prep Business.
            # Possiamo simulare un evento, ma non possiamo forzare l'invio di webhook da qui.
            
            self.stdout.write(self.style.WARNING(
                f'Non è possibile inviare direttamente un evento di test al webhook {webhook_id}.'
                f'\nPer testare se il webhook funziona:'
                f'\n1. Effettua una modifica a una spedizione in Prep Business'
                f'\n2. Controlla nei log di Railway se l\'evento viene ricevuto'
                f'\n3. Verifica che l\'evento appaia nella dashboard di questo sistema'
            ))
            self.stdout.write(self.style.WARNING(
                f'\nPer controllare il funzionamento del webhook:'
                f'\n- Verifica che l\'URL sia raggiungibile da internet'
                f'\n- Assicurati che il webhook sia configurato correttamente'
                f'\n- Controlla i log di Railway per eventuali errori'
            ))
            
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Errore durante il test del webhook: {str(e)}')) 