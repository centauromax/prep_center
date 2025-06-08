#!/usr/bin/env python3

import os
import sys
import django

# Setup Django
sys.path.append('/Users/adriano/WORK/sviluppo/prep_center/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'prep_center.settings')

try:
    django.setup()
    print("✅ Django setup completato")
except Exception as e:
    print(f"❌ Errore Django setup: {e}")
    exit(1)

# Test importazioni
try:
    from prep_management.chat_manager import ChatManager
    print("✅ ChatManager importato correttamente")
except Exception as e:
    print(f"❌ Errore importazione ChatManager: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

try:
    from prep_management.models import TelegramNotification, TelegramConversation, TelegramChatMessage
    print("✅ Modelli importati correttamente")
except Exception as e:
    print(f"❌ Errore importazione modelli: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

try:
    from prep_management.services import TelegramService, ADMIN_EMAIL
    print("✅ TelegramService importato correttamente")
    print(f"📧 ADMIN_EMAIL: {ADMIN_EMAIL}")
except Exception as e:
    print(f"❌ Errore importazione TelegramService: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# Test creazione ChatManager
try:
    chat_manager = ChatManager()
    print("✅ ChatManager creato correttamente")
except Exception as e:
    print(f"❌ Errore creazione ChatManager: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# Test con utente fittizio per vedere l'errore
print("\n🧪 Test simulazione messaggio cliente...")

# Crea un utente di test se non esiste
from prep_management.models import TelegramNotification

test_chat_id = 999999
test_email = "test@example.com"

# Pulisci eventuali utenti di test precedenti
TelegramNotification.objects.filter(chat_id=test_chat_id).delete()

# Crea utente di test
test_user = TelegramNotification.objects.create(
    chat_id=test_chat_id,
    email=test_email,
    is_active=True,
    language_code='it'
)
print(f"✅ Utente test creato: {test_user}")

# Test handle_customer_message
try:
    result = chat_manager.handle_customer_message(test_chat_id, "Messaggio di test")
    print(f"✅ handle_customer_message risultato: {result}")
except Exception as e:
    print(f"❌ Errore handle_customer_message: {e}")
    import traceback
    traceback.print_exc()

# Cleanup
test_user.delete()
print("✅ Cleanup completato") 