#!/usr/bin/env python
"""
Script per invocare direttamente il comando setup_webhook.
Questo script aggira il sistema di gestione dei comandi di Django
e chiama direttamente i metodi della classe Command.

Uso:
    python scripts/invoke_webhook_setup.py list
    python scripts/invoke_webhook_setup.py create
    python scripts/invoke_webhook_setup.py delete WEBHOOK_ID
"""

import os
import sys
import django
from io import StringIO

# Setup dell'ambiente Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'prep_center.settings')
django.setup()

# Importa il comando setup_webhook
from prep_management.management.commands.setup_webhook import Command

def setup_stdout_capture():
    """Configura la cattura dell'output standard per recuperare i messaggi."""
    old_stdout = sys.stdout
    redirected_output = StringIO()
    sys.stdout = redirected_output
    return old_stdout, redirected_output

def restore_stdout(old_stdout):
    """Ripristina l'output standard originale."""
    sys.stdout = old_stdout

def invoke_list_webhooks():
    """Elenca i webhook configurati."""
    cmd = Command()
    
    # Cattura l'output
    old_stdout, redirected_output = setup_stdout_capture()
    
    try:
        # Simuliamo l'opzione --list
        options = {'list': True, 'delete': None, 'url': None, 'merchant': None, 'test': False, 'webhook_id': None}
        cmd.handle(**options)
    finally:
        # Ripristina l'output standard
        restore_stdout(old_stdout)
    
    # Stampa l'output catturato
    output = redirected_output.getvalue()
    print(output)
    return output

def invoke_create_webhook(url=None, merchant_id=None):
    """Crea un nuovo webhook."""
    cmd = Command()
    
    # Cattura l'output
    old_stdout, redirected_output = setup_stdout_capture()
    
    try:
        # Simuliamo l'opzione per creare
        options = {
            'list': False, 
            'delete': None, 
            'url': url, 
            'merchant': merchant_id, 
            'test': False, 
            'webhook_id': None
        }
        cmd.handle(**options)
    finally:
        # Ripristina l'output standard
        restore_stdout(old_stdout)
    
    # Stampa l'output catturato
    output = redirected_output.getvalue()
    print(output)
    return output

def invoke_delete_webhook(webhook_id, merchant_id=None):
    """Elimina un webhook."""
    cmd = Command()
    
    # Cattura l'output
    old_stdout, redirected_output = setup_stdout_capture()
    
    try:
        # Simuliamo l'opzione --delete
        options = {
            'list': False, 
            'delete': webhook_id, 
            'url': None, 
            'merchant': merchant_id, 
            'test': False, 
            'webhook_id': None
        }
        cmd.handle(**options)
    finally:
        # Ripristina l'output standard
        restore_stdout(old_stdout)
    
    # Stampa l'output catturato
    output = redirected_output.getvalue()
    print(output)
    return output

def invoke_test_webhook(webhook_id=None, merchant_id=None):
    """Testa un webhook."""
    cmd = Command()
    
    # Cattura l'output
    old_stdout, redirected_output = setup_stdout_capture()
    
    try:
        # Simuliamo l'opzione --test
        options = {
            'list': False, 
            'delete': None, 
            'url': None, 
            'merchant': merchant_id, 
            'test': True, 
            'webhook_id': webhook_id
        }
        cmd.handle(**options)
    finally:
        # Ripristina l'output standard
        restore_stdout(old_stdout)
    
    # Stampa l'output catturato
    output = redirected_output.getvalue()
    print(output)
    return output

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Errore: Devi specificare un'azione (list, create, delete, test)")
        sys.exit(1)
        
    action = sys.argv[1].lower()
    
    try:
        if action == "list":
            invoke_list_webhooks()
        elif action == "create":
            url = sys.argv[2] if len(sys.argv) > 2 else None
            merchant_id = int(sys.argv[3]) if len(sys.argv) > 3 else None
            invoke_create_webhook(url, merchant_id)
        elif action == "delete":
            if len(sys.argv) < 3:
                print("Errore: Devi specificare l'ID del webhook da eliminare")
                sys.exit(1)
            webhook_id = int(sys.argv[2])
            merchant_id = int(sys.argv[3]) if len(sys.argv) > 3 else None
            invoke_delete_webhook(webhook_id, merchant_id)
        elif action == "test":
            webhook_id = int(sys.argv[2]) if len(sys.argv) > 2 else None
            merchant_id = int(sys.argv[3]) if len(sys.argv) > 3 else None
            invoke_test_webhook(webhook_id, merchant_id)
        else:
            print(f"Errore: Azione '{action}' non riconosciuta. Usa 'list', 'create', 'delete' o 'test'")
            sys.exit(1)
    except Exception as e:
        print(f"Errore durante l'esecuzione del comando: {str(e)}")
        sys.exit(1) 