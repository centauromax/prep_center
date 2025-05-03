"""
Modulo per gestire i webhook di Prep Business in modo programmatico.
Questo modulo può essere importato da qualsiasi punto dell'applicazione
per eseguire operazioni sui webhook senza dover passare dal sistema
di gestione comandi di Django.
"""

import os
import logging
from io import StringIO
import sys

logger = logging.getLogger('prep_management')

def setup_django_env():
    """Setup dell'ambiente Django se necessario."""
    import django
    if not hasattr(django, 'apps'):
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'prep_center.settings')
        django.setup()

def get_command_class():
    """Importa la classe Command da setup_webhook."""
    setup_django_env()
    try:
        from prep_management.management.commands.setup_webhook import Command
        return Command
    except ImportError as e:
        logger.error(f"Errore nell'importazione del comando setup_webhook: {str(e)}")
        raise ImportError(f"Impossibile importare il comando setup_webhook: {str(e)}")

def capture_output(func):
    """Decorator per catturare l'output di una funzione."""
    def wrapper(*args, **kwargs):
        # Cattura l'output
        old_stdout = sys.stdout
        redirected_output = StringIO()
        sys.stdout = redirected_output
        
        try:
            result = func(*args, **kwargs)
            # Aggiungi l'output catturato al risultato
            output = redirected_output.getvalue()
            if isinstance(result, dict):
                result['output'] = output
            else:
                result = {'result': result, 'output': output}
            return result
        finally:
            # Ripristina l'output standard
            sys.stdout = old_stdout
    
    return wrapper

@capture_output
def list_webhooks(merchant_id=None):
    """
    Elenca i webhook configurati.
    
    Args:
        merchant_id: ID del merchant per cui elencare i webhook (opzionale)
        
    Returns:
        dict: Risultato dell'operazione con l'output del comando
    """
    try:
        Command = get_command_class()
        cmd = Command()
        
        # Simula opzioni
        options = {
            'list': True, 
            'delete': None, 
            'url': None, 
            'merchant': merchant_id, 
            'test': False, 
            'webhook_id': None
        }
        
        cmd.handle(**options)
        return {'success': True}
    except Exception as e:
        logger.error(f"Errore nell'elenco dei webhook: {str(e)}")
        return {'success': False, 'error': str(e)}

@capture_output
def create_webhook(url=None, merchant_id=None):
    """
    Crea un nuovo webhook.
    
    Args:
        url: URL del webhook (opzionale, usa automaticamente l'URL di Railway se non specificato)
        merchant_id: ID del merchant per cui creare il webhook (opzionale)
        
    Returns:
        dict: Risultato dell'operazione con l'output del comando
    """
    try:
        Command = get_command_class()
        cmd = Command()
        
        # Simula opzioni
        options = {
            'list': False, 
            'delete': None, 
            'url': url, 
            'merchant': merchant_id, 
            'test': False, 
            'webhook_id': None
        }
        
        cmd.handle(**options)
        return {'success': True}
    except Exception as e:
        logger.error(f"Errore nella creazione del webhook: {str(e)}")
        return {'success': False, 'error': str(e)}

@capture_output
def update_webhook(webhook_id, url, merchant_id=None):
    """
    Aggiorna un webhook esistente.
    
    Args:
        webhook_id: ID del webhook da aggiornare
        url: Nuovo URL del webhook
        merchant_id: ID del merchant (opzionale)
        
    Returns:
        dict: Risultato dell'operazione con l'output del comando
    """
    try:
        # Importa direttamente i componenti necessari per l'aggiornamento
        setup_django_env()
        from libs.prepbusiness.client import PrepBusinessClient
        from libs.config import (
            PREP_BUSINESS_API_URL,
            PREP_BUSINESS_API_KEY,
            PREP_BUSINESS_API_TIMEOUT,
        )
        
        # Estrai dominio dall'URL API
        api_url = PREP_BUSINESS_API_URL
        if not api_url:
            logger.error('PREP_BUSINESS_API_URL non configurato')
            return {'success': False, 'error': 'API URL non configurato'}
            
        domain = api_url.replace('https://', '').replace('http://', '').split('/')[0]
        
        # Crea cliente Prep Business
        client = PrepBusinessClient(
            api_key=PREP_BUSINESS_API_KEY,
            company_domain=domain,
            timeout=PREP_BUSINESS_API_TIMEOUT,
        )
        
        # Aggiorna il webhook attivando tutti gli eventi disponibili
        if merchant_id:
            response = client.update_merchant_webhook(
                merchant_id=merchant_id,
                webhook_id=webhook_id,
                url=url,
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
            print(f'Webhook aggiornato per il merchant {merchant_id}: {url}')
        else:
            response = client.update_webhook(
                webhook_id=webhook_id,
                url=url,
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
            print(f'Webhook globale aggiornato: {url}')
            
        # Mostra dettagli webhook
        webhook = response.webhook
        print('-' * 50)
        print('Dettagli webhook:')
        print(f'ID: {webhook.id}')
        print(f'URL: {webhook.url}')
        print('Eventi configurati:')
        
        # Mostra gli eventi attivi
        for field, value in webhook.__dict__.items():
            if field.startswith('receives_') and value:
                event_name = field.replace('receives_', '')
                print(f'  - {event_name}')
                
        return {'success': True, 'webhook': webhook}
    except Exception as e:
        logger.error(f"Errore nell'aggiornamento del webhook: {str(e)}")
        return {'success': False, 'error': str(e)}

@capture_output
def delete_webhook(webhook_id, merchant_id=None):
    """
    Elimina un webhook.
    
    Args:
        webhook_id: ID del webhook da eliminare
        merchant_id: ID del merchant (opzionale)
        
    Returns:
        dict: Risultato dell'operazione con l'output del comando
    """
    try:
        Command = get_command_class()
        cmd = Command()
        
        # Simula opzioni
        options = {
            'list': False, 
            'delete': webhook_id, 
            'url': None, 
            'merchant': merchant_id, 
            'test': False, 
            'webhook_id': None
        }
        
        cmd.handle(**options)
        return {'success': True}
    except Exception as e:
        logger.error(f"Errore nell'eliminazione del webhook: {str(e)}")
        return {'success': False, 'error': str(e)}

@capture_output
def test_webhook(webhook_id=None, merchant_id=None):
    """
    Testa un webhook.
    
    Args:
        webhook_id: ID del webhook da testare (opzionale)
        merchant_id: ID del merchant (opzionale)
        
    Returns:
        dict: Risultato dell'operazione con l'output del comando
    """
    try:
        Command = get_command_class()
        cmd = Command()
        
        # Simula opzioni
        options = {
            'list': False, 
            'delete': None, 
            'url': None, 
            'merchant': merchant_id, 
            'test': True, 
            'webhook_id': webhook_id
        }
        
        cmd.handle(**options)
        return {'success': True}
    except Exception as e:
        logger.error(f"Errore nel test del webhook: {str(e)}")
        return {'success': False, 'error': str(e)} 