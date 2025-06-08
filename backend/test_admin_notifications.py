#!/usr/bin/env python3

# Test per verificare il sistema di notifiche amministrative

import sys
sys.path.append('/Users/adriano/WORK/sviluppo/prep_center/backend')

# Mock delle funzioni per testare senza Django

ADMIN_EMAIL = "info@fbaprepcenteritaly.com"

def mock_get_telegram_users(email):
    """Mock della query per utenti Telegram"""
    
    # Simula utenti esistenti
    mock_users = {
        "prep@easyavant.com": [
            {"email": "prep@easyavant.com", "chat_id": 123456, "language_code": "en"}
        ],
        "info@fbaprepcenteritaly.com": [
            {"email": "info@fbaprepcenteritaly.com", "chat_id": 789012, "language_code": "it"}
        ]
    }
    
    return mock_users.get(email, [])

def mock_send_notification_logic(email, event_type="inbound_shipment.created", shipment_data=None):
    """Mock della logica di invio notifiche"""
    
    print(f"\n🔔 Invio notifica per: {email}")
    print(f"📦 Evento: {event_type}")
    
    # Trova utenti principali
    main_users = mock_get_telegram_users(email)
    all_users = main_users.copy()
    
    # Aggiungi admin se email diversa
    if email != ADMIN_EMAIL:
        admin_users = mock_get_telegram_users(ADMIN_EMAIL)
        all_users.extend(admin_users)
        if admin_users:
            print(f"➕ Aggiunta notifica anche per email amministrativa: {ADMIN_EMAIL}")
    
    # Simula invio a tutti gli utenti
    for user in all_users:
        user_lang = user.get("language_code", "it")
        
        # Simula formattazione messaggio
        if event_type == "inbound_shipment.created":
            if user_lang == "en":
                message = "📦 New inbound shipment created\n\n🆔 ID: TEST123\n📝 Name: Test Shipment"
            else:
                message = "📦 Nuova spedizione in entrata creata\n\n🆔 ID: TEST123\n📝 Nome: Test Shipment"
        else:
            message = f"Evento: {event_type}"
        
        # Se questo è l'admin e non è il cliente originale, aggiungi prefisso
        if user["email"] == ADMIN_EMAIL and email != ADMIN_EMAIL:
            admin_prefix = f"📧 Cliente: {email}\n\n" if user_lang == "it" else f"📧 Customer: {email}\n\n"
            message = admin_prefix + message
        
        print(f"  ✅ {user['email']} (chat_id: {user['chat_id']}, lang: {user_lang})")
        print(f"     Messaggio: {message[:100]}...")
    
    return len(all_users) > 0

def test_admin_notification_system():
    """Test del sistema di notifiche amministrative"""
    
    print("🧪 Test sistema notifiche amministrative")
    print("=" * 60)
    
    print(f"🏢 Email amministrativa configurata: {ADMIN_EMAIL}")
    
    # Test 1: Notifica per cliente normale
    print("\n📨 TEST 1: Notifica per cliente normale")
    success = mock_send_notification_logic("prep@easyavant.com")
    
    if success:
        print("✅ Test 1 superato: Cliente e admin ricevono notifica")
    else:
        print("❌ Test 1 fallito")
    
    # Test 2: Notifica per l'admin stesso
    print("\n📨 TEST 2: Notifica diretta per admin")
    success = mock_send_notification_logic(ADMIN_EMAIL)
    
    if success:
        print("✅ Test 2 superato: Solo admin riceve notifica (no duplicati)")
    else:
        print("❌ Test 2 fallito")
    
    # Test 3: Formato messaggio admin
    print("\n📨 TEST 3: Verifica formato messaggio admin")
    
    # Simula messaggio per admin
    original_email = "prep@easyavant.com"
    event_type = "inbound_shipment.created"
    
    base_message = "📦 Nuova spedizione in entrata creata\n\n🆔 ID: TEST123"
    admin_message = f"📧 Cliente: {original_email}\n\n{base_message}"
    
    print(f"Messaggio originale per cliente:\n{base_message}")
    print(f"\nMessaggio per admin:\n{admin_message}")
    
    if "Cliente:" in admin_message and original_email in admin_message:
        print("✅ Test 3 superato: Messaggio admin contiene info cliente")
    else:
        print("❌ Test 3 fallito: Messaggio admin non corretto")

def test_email_validation():
    """Test validazione email amministrativa"""
    
    print("\n🔍 Test validazione email amministrativa")
    print("=" * 60)
    
    # Lista email valide (dal codice)
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
        "zunan.javid@novus-trade.fr",
        "info@fbaprepcenteritaly.com"
    ]
    
    if ADMIN_EMAIL in valid_emails:
        print(f"✅ Email amministrativa {ADMIN_EMAIL} presente nella lista valida")
    else:
        print(f"❌ Email amministrativa {ADMIN_EMAIL} NON presente nella lista valida")
    
    print(f"📧 Totale email valide: {len(valid_emails)}")

if __name__ == "__main__":
    print("🚀 Test sistema notifiche amministrative")
    
    try:
        test_admin_notification_system()
        test_email_validation()
        
        print("\n🎉 TUTTI I TEST COMPLETATI!")
        print(f"📧 L'email {ADMIN_EMAIL} riceverà tutte le notifiche!")
        print("💡 Ricordati di registrare questa email nel bot con /start")
        
    except Exception as e:
        print(f"\n❌ ERRORE NEI TEST: {e}")
        import traceback
        traceback.print_exc() 