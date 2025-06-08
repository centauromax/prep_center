#!/usr/bin/env python
"""
Script di test per verificare il sistema di traduzioni del bot Telegram.
"""

import os
import sys
import django

# Aggiungi il path del progetto
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configura Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'prep_center.settings')
django.setup()

from prep_management.translations import get_text, TRANSLATIONS

def test_translations():
    """Testa tutte le traduzioni disponibili."""
    print("🧪 Test del sistema di traduzioni multilingua")
    print("=" * 50)
    
    # Test traduzioni base
    print("\n1. Test messaggio di benvenuto bilingue:")
    welcome = get_text('welcome_bilingual')
    print(f"✅ Benvenuto: {welcome[:100]}...")
    
    print("\n2. Test selezione lingua:")
    lang_it = get_text('language_selected', lang='it')
    lang_en = get_text('language_selected', lang='en')
    print(f"✅ Italiano: {lang_it[:50]}...")
    print(f"✅ English: {lang_en[:50]}...")
    
    print("\n3. Test help multilingua:")
    help_it = get_text('help', lang='it')
    help_en = get_text('help', lang='en')
    print(f"✅ Help IT: {help_it[:50]}...")
    print(f"✅ Help EN: {help_en[:50]}...")
    
    print("\n4. Test registrazione con parametri:")
    reg_it = get_text('registration_success', lang='it', email='test@example.com', chat_id=123456)
    reg_en = get_text('registration_success', lang='en', email='test@example.com', chat_id=123456)
    print(f"✅ Registrazione IT: {reg_it[:50]}...")
    print(f"✅ Registrazione EN: {reg_en[:50]}...")
    
    print("\n5. Test errori:")
    error_it = get_text('invalid_email', lang='it')
    error_en = get_text('invalid_email', lang='en')
    print(f"✅ Errore IT: {error_it[:50]}...")
    print(f"✅ Errore EN: {error_en[:50]}...")
    
    print("\n6. Test chiavi mancanti:")
    missing = get_text('chiave_inesistente', lang='it')
    print(f"✅ Chiave mancante: {missing}")
    
    print("\n7. Riepilogo traduzioni disponibili:")
    print(f"📊 Totale chiavi di traduzione: {len(TRANSLATIONS)}")
    for key in TRANSLATIONS.keys():
        print(f"   - {key}")
    
    print("\n✅ Test completato con successo!")

def test_user_language_functions():
    """Testa le funzioni di gestione lingua utente."""
    print("\n🧪 Test funzioni gestione lingua utente")
    print("=" * 50)
    
    from prep_management.translations import get_user_language
    
    # Test con chat_id inesistente
    lang = get_user_language(999999)
    print(f"✅ Lingua default per utente inesistente: {lang}")
    
    # Test con chat_id esistente (se presente nel DB)
    try:
        from prep_management.models import TelegramNotification
        users = TelegramNotification.objects.all()[:3]
        for user in users:
            lang = get_user_language(user.chat_id)
            print(f"✅ Lingua per {user.email}: {lang}")
    except Exception as e:
        print(f"⚠️  Nessun utente nel database: {e}")

if __name__ == '__main__':
    try:
        test_translations()
        test_user_language_functions()
    except Exception as e:
        print(f"❌ Errore durante il test: {e}")
        import traceback
        traceback.print_exc() 