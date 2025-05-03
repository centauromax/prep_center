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