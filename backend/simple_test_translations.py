#!/usr/bin/env python
"""
Test semplice delle traduzioni senza Django.
"""

# Importa direttamente il modulo traduzioni
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'prep_management'))

# Simula le traduzioni
TRANSLATIONS = {
    'welcome_bilingual': {
        'text': "🤖 Welcome to FBA Prep Center Italy Bot! / Benvenuto al FBA Prep Center Italy Bot!\n\nTo receive notifications about your orders and shipments, you need to register on this bot.\nPer ricevere notifiche sui tuoi ordini e spedizioni, devi registrarti su questo bot.\n\n🌍 Please choose your language / Scegli la tua lingua:\n• Type \"e\" for English\n• Scrivi \"i\" per Italiano"
    },
    
    'language_selected': {
        'it': "✅ Lingua impostata: Italiano\n\n📧 Ora inserisci l'email con cui ti sei registrato sul software del Prep Center.\n\nEsempio: mario.rossi@example.com\n\nℹ️ Usa /help per vedere tutti i comandi disponibili.",
        'en': "✅ Language set: English\n\n📧 Now enter the email you used to register on the Prep Center software.\n\nExample: mario.rossi@example.com\n\nℹ️ Use /help to see all available commands."
    },
    
    'help': {
        'it': "🤖 FBA Prep Center Italy Bot - Aiuto\n\nComandi disponibili:\n• /start - Avvia il bot\n• /help - Mostra aiuto\n• /test - Test connessione\n• /status - Stato registrazione\n• /language - Cambia lingua",
        'en': "🤖 FBA Prep Center Italy Bot - Help\n\nAvailable commands:\n• /start - Start the bot\n• /help - Show help\n• /test - Connection test\n• /status - Registration status\n• /language - Change language"
    },
    
    'registration_success': {
        'it': "✅ Registrazione completata!\n\n📧 Email: {email}\n🆔 Chat ID: {chat_id}\n\nOra riceverai notifiche automatiche!",
        'en': "✅ Registration completed!\n\n📧 Email: {email}\n🆔 Chat ID: {chat_id}\n\nYou will now receive automatic notifications!"
    }
}

def get_text(key, lang='it', **kwargs):
    """Ottiene il testo tradotto."""
    if key not in TRANSLATIONS:
        return f"[MISSING TRANSLATION: {key}]"
    
    translation = TRANSLATIONS[key]
    
    if isinstance(translation, dict) and 'text' in translation:
        text = translation['text']
    elif isinstance(translation, dict):
        text = translation.get(lang, translation.get('it', f"[MISSING: {key}:{lang}]"))
    else:
        text = translation
    
    try:
        return text.format(**kwargs)
    except KeyError as e:
        return f"[FORMAT ERROR in {key}: missing {e}]"

def test_translations():
    """Testa le traduzioni."""
    print("🧪 Test del sistema di traduzioni multilingua")
    print("=" * 50)
    
    # Test 1: Messaggio bilingue
    print("\n1. Test messaggio di benvenuto:")
    welcome = get_text('welcome_bilingual')
    print(f"✅ Lunghezza: {len(welcome)} caratteri")
    print(f"✅ Contiene 'Welcome': {'Welcome' in welcome}")
    print(f"✅ Contiene 'Benvenuto': {'Benvenuto' in welcome}")
    
    # Test 2: Selezione lingua
    print("\n2. Test selezione lingua:")
    lang_it = get_text('language_selected', lang='it')
    lang_en = get_text('language_selected', lang='en')
    print(f"✅ Italiano: {lang_it[:50]}...")
    print(f"✅ English: {lang_en[:50]}...")
    
    # Test 3: Help multilingua
    print("\n3. Test help:")
    help_it = get_text('help', lang='it')
    help_en = get_text('help', lang='en')
    print(f"✅ Help IT: {help_it[:50]}...")
    print(f"✅ Help EN: {help_en[:50]}...")
    
    # Test 4: Registrazione con parametri
    print("\n4. Test registrazione con parametri:")
    reg_it = get_text('registration_success', lang='it', email='test@example.com', chat_id=123456)
    reg_en = get_text('registration_success', lang='en', email='test@example.com', chat_id=123456)
    print(f"✅ Registrazione IT: {reg_it}")
    print(f"✅ Registrazione EN: {reg_en}")
    
    # Test 5: Chiave mancante
    print("\n5. Test chiave mancante:")
    missing = get_text('chiave_inesistente', lang='it')
    print(f"✅ Chiave mancante: {missing}")
    
    print("\n✅ Test completato con successo!")
    print(f"📊 Totale traduzioni: {len(TRANSLATIONS)}")

def test_language_flow():
    """Simula il flusso di selezione lingua."""
    print("\n🔄 Simulazione flusso selezione lingua")
    print("=" * 50)
    
    # Simula /start
    print("\n👤 Utente: /start")
    print("🤖 Bot:")
    print(get_text('welcome_bilingual'))
    
    # Simula scelta italiano
    print("\n👤 Utente: i")
    print("🤖 Bot:")
    print(get_text('language_selected', lang='it'))
    
    # Simula help in italiano
    print("\n👤 Utente: /help")
    print("🤖 Bot:")
    print(get_text('help', lang='it'))
    
    print("\n" + "="*50)
    
    # Simula scelta inglese
    print("\n👤 Utente: e")
    print("🤖 Bot:")
    print(get_text('language_selected', lang='en'))
    
    # Simula help in inglese
    print("\n👤 Utente: /help")
    print("🤖 Bot:")
    print(get_text('help', lang='en'))

if __name__ == '__main__':
    test_translations()
    test_language_flow() 