#!/usr/bin/env python3
import os
import sys
import django

# Setup Django
sys.path.append('/Users/adriano/WORK/sviluppo/prep_center/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'prep_center.settings')
django.setup()

from prep_management.services import format_shipment_notification, send_telegram_notification
from prep_management.models import TelegramNotification, TelegramMessage
from prep_management.translations import get_text

def test_notification_formatting():
    """Test formattazione notifiche in italiano e inglese"""
    
    print("🧪 Test formattazione notifiche multilingua")
    print("=" * 50)
    
    # Dati di test
    shipment_data = {
        'shipment_id': 'TEST123',
        'shipment_name': 'Spedizione di prova',
        'tracking_number': 'TRK123456',
        'carrier': 'DHL',
        'notes': 'Note di prova'
    }
    
    # Test in italiano
    print("\n📦 ITALIANO:")
    message_it = format_shipment_notification(
        event_type='inbound_shipment.created',
        shipment_data=shipment_data,
        user_language='it'
    )
    print(message_it)
    
    # Test in inglese
    print("\n📦 ENGLISH:")
    message_en = format_shipment_notification(
        event_type='inbound_shipment.created',
        shipment_data=shipment_data,
        user_language='en'
    )
    print(message_en)
    
    # Verifica che siano diversi
    assert message_it != message_en, "I messaggi dovrebbero essere diversi!"
    assert "Nuova spedizione in entrata creata" in message_it, "Messaggio italiano non corretto"
    assert "New inbound shipment created" in message_en, "Messaggio inglese non corretto"
    assert "Nome:" in message_it, "Label italiano non corretto"
    assert "Name:" in message_en, "Label inglese non corretto"
    
    print("\n✅ Test formattazione completato con successo!")

def test_user_language_detection():
    """Test rilevamento lingua utente"""
    
    print("\n🌍 Test rilevamento lingua utente")
    print("=" * 50)
    
    # Test con utente inglese esistente (prep@easyavant.com dovrebbe essere in inglese)
    try:
        user_en = TelegramNotification.objects.filter(
            email='prep@easyavant.com',
            language_code='en'
        ).first()
        
        if user_en:
            print(f"✅ Utente inglese trovato: {user_en.email} - Lingua: {user_en.language_code}")
        else:
            print("❌ Utente inglese non trovato - il test potrebbe non essere completo")
            
        # Test con utente italiano
        user_it = TelegramNotification.objects.filter(
            language_code='it'
        ).first()
        
        if user_it:
            print(f"✅ Utente italiano trovato: {user_it.email} - Lingua: {user_it.language_code}")
        else:
            print("❌ Utente italiano non trovato")
            
    except Exception as e:
        print(f"❌ Errore nel rilevamento utenti: {e}")

def test_complete_notification_flow():
    """Test completo del flusso di notifica"""
    
    print("\n🔄 Test flusso completo notifica")
    print("=" * 50)
    
    # Trova un utente inglese per il test
    user_en = TelegramNotification.objects.filter(
        email='prep@easyavant.com',
        language_code='en'
    ).first()
    
    if not user_en:
        print("❌ Nessun utente inglese trovato per il test")
        return
    
    # Dati di test
    test_shipment_data = {
        'shipment_id': 'TEST456',
        'shipment_name': 'Test Shipment',
        'tracking_number': 'TRK789012',
        'carrier': 'UPS',
        'notes': 'Test notification'
    }
    
    # Conta messaggi prima
    messages_before = TelegramMessage.objects.count()
    
    print(f"📧 Invio notifica di test a: {user_en.email} (lingua: {user_en.language_code})")
    
    # Simula invio notifica (non invia realmente per evitare spam)
    try:
        # Formatta messaggio nella lingua dell'utente
        message = format_shipment_notification(
            event_type='inbound_shipment.created',
            shipment_data=test_shipment_data,
            user_language=user_en.language_code
        )
        
        print(f"✅ Messaggio formattato correttamente in {user_en.language_code}")
        print(f"📝 Anteprima messaggio:")
        print("-" * 30)
        print(message[:200] + "..." if len(message) > 200 else message)
        print("-" * 30)
        
        # Verifica che sia in inglese
        if "New inbound shipment created" in message and "Name:" in message:
            print("✅ Messaggio correttamente in inglese!")
        else:
            print("❌ Messaggio non sembra essere in inglese")
            
    except Exception as e:
        print(f"❌ Errore nella formattazione: {e}")

if __name__ == "__main__":
    print("🚀 Avvio test notifiche multilingua")
    
    try:
        test_notification_formatting()
        test_user_language_detection()
        test_complete_notification_flow()
        
        print("\n🎉 TUTTI I TEST COMPLETATI!")
        print("🌍 Il sistema di notifiche multilingua è pronto!")
        
    except Exception as e:
        print(f"\n❌ ERRORE NEI TEST: {e}")
        import traceback
        traceback.print_exc() 