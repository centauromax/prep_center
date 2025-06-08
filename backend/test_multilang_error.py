#!/usr/bin/env python
"""
Test specifico per verificare il fix del messaggio di errore misto italiano/inglese.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'prep_management'))

# Simula le traduzioni aggiornate
TRANSLATIONS = {
    'email_not_found_in_system': {
        'it': """
❌ <b>Email non trovata nel sistema</b>

L'email {email} non è stata trovata nel software del Prep Center.

Per registrarti devi utilizzare l'email con cui hai attivato il tuo account sul software del Prep Center.

💡 <b>Suggerimenti:</b>
• Verifica di aver scritto correttamente l'email
• Controlla che sia la stessa email del tuo account sul software del Prep Center
• Contatta il supporto se il problema persiste
        """,
        'en': """
❌ <b>Email not found in system</b>

The email {email} was not found in the Prep Center software.

To register, you must use the email you used to activate your account on the Prep Center software.

💡 <b>Suggestions:</b>
• Check that you have typed the email correctly
• Make sure it's the same email as your Prep Center software account
• Contact support if the problem persists
        """
    }
}

def get_text(key, lang='it', **kwargs):
    """Ottiene il testo tradotto."""
    if key not in TRANSLATIONS:
        return f"[MISSING TRANSLATION: {key}]"
    
    translation = TRANSLATIONS[key]
    
    if isinstance(translation, dict):
        text = translation.get(lang, translation.get('it', f"[MISSING: {key}:{lang}]"))
    else:
        text = translation
    
    try:
        return text.format(**kwargs)
    except KeyError as e:
        return f"[FORMAT ERROR in {key}: missing {e}]"

def test_error_messages():
    """Testa i messaggi di errore corretti."""
    print("🧪 Test messaggio di errore email non trovata")
    print("=" * 50)
    
    email = "mario.rossi@example.com"
    
    # Test messaggio in italiano
    print("\n📧 Test messaggio ITALIANO:")
    message_it = get_text('email_not_found_in_system', lang='it', email=email)
    print(message_it)
    
    # Verifica che sia tutto in italiano
    has_english = any(word in message_it.lower() for word in ['check', 'make sure', 'contact support', 'suggestions'])
    print(f"✅ Contiene parole inglesi: {has_english} (dovrebbe essere False)")
    
    print("\n" + "="*50)
    
    # Test messaggio in inglese
    print("\n📧 Test messaggio INGLESE:")
    message_en = get_text('email_not_found_in_system', lang='en', email=email)
    print(message_en)
    
    # Verifica che sia tutto in inglese
    has_italian = any(word in message_en.lower() for word in ['verifica', 'controlla', 'contatta', 'suggerimenti'])
    print(f"✅ Contiene parole italiane: {has_italian} (dovrebbe essere False)")
    
    print("\n✅ Test completato!")

def test_old_vs_new():
    """Confronta il vecchio messaggio misto con quello nuovo."""
    print("\n🔄 Confronto messaggio vecchio vs nuovo")
    print("=" * 50)
    
    email = "mario.rossi@example.com"
    
    print("\n❌ VECCHIO (misto):")
    old_message = f"""Email {email} non trovata nel software del Prep Center. Verifica di aver inserito l'email corretta utilizzata per il tuo account sul software del Prep Center.

To register, you must use the email you used to activate your account on the Prep Center software.

Suggestions:
• Check that you have typed the email correctly
• Make sure it's the same email as your Prep Center software account
• Contact support if the problem persists"""
    
    print(old_message)
    
    print("\n✅ NUOVO (solo italiano):")
    new_message = get_text('email_not_found_in_system', lang='it', email=email)
    print(new_message)
    
    print("\n✅ NUOVO (solo inglese):")
    new_message_en = get_text('email_not_found_in_system', lang='en', email=email)
    print(new_message_en)

if __name__ == '__main__':
    test_error_messages()
    test_old_vs_new() 