"""
Sistema di traduzioni per il bot Telegram multilingua.
Supporta Italiano (it) e Inglese (en).
"""

TRANSLATIONS = {
    # Messaggio di benvenuto bilingue
    'welcome_bilingual': {
        'text': "🤖 Welcome to FBA Prep Center Italy Bot! / Benvenuto al FBA Prep Center Italy Bot!\n\nTo receive notifications about your orders and shipments, you need to register on this bot.\nPer ricevere notifiche sui tuoi ordini e spedizioni, devi registrarti su questo bot.\n\n🌍 Please choose your language / Scegli la tua lingua:\n• Type \"e\" for English\n• Scrivi \"i\" per Italiano"
    },
    
    # Messaggio dopo scelta lingua
    'language_selected': {
        'it': """
✅ <b>Lingua impostata: Italiano</b>

📧 Ora inserisci l'email con cui ti sei registrato sul software del Prep Center.

Esempio: <code>mario.rossi@example.com</code>

ℹ️ Usa /help per vedere tutti i comandi disponibili.
        """,
        'en': """
✅ <b>Language set: English</b>

📧 Now enter the email you used to register on the Prep Center software.

Example: <code>mario.rossi@example.com</code>

ℹ️ Use /help to see all available commands.
        """
    },
    
    # Comando help
    'help': {
        'it': """
🤖 <b>FBA Prep Center Italy Bot - Aiuto</b>

<b>Comandi disponibili:</b>
• <code>/start</code> - Avvia il bot e ottieni istruzioni
• <code>/help</code> - Mostra questo messaggio di aiuto
• <code>/test</code> - Invia un messaggio di test
• <code>/status</code> - Controlla lo stato della tua registrazione
• <code>/language</code> - Cambia lingua

<b>Per registrarti:</b>
1. Invia la tua email del Prep Center
2. Conferma la registrazione
3. Inizia a ricevere notifiche!

<b>Tipi di notifiche:</b>
📦 Spedizioni in entrata
📤 Spedizioni in uscita
🛒 Ordini
📋 Aggiornamenti generali

<b>Supporto:</b>
Per problemi o domande, contatta il supporto FBA Prep Center Italy.
        """,
        'en': """
🤖 <b>FBA Prep Center Italy Bot - Help</b>

<b>Available commands:</b>
• <code>/start</code> - Start the bot and get instructions
• <code>/help</code> - Show this help message
• <code>/test</code> - Send a test message
• <code>/status</code> - Check your registration status
• <code>/language</code> - Change language

<b>To register:</b>
1. Send your Prep Center email
2. Confirm registration
3. Start receiving notifications!

<b>Notification types:</b>
📦 Inbound shipments
📤 Outbound shipments
🛒 Orders
📋 General updates

<b>Support:</b>
For issues or questions, contact FBA Prep Center Italy support.
        """
    },
    
    # Email non valida
    'invalid_email': {
        'it': """
❌ <b>Email non valida</b>

Invia una email valida nel formato: <code>nome@dominio.com</code>
        """,
        'en': """
❌ <b>Invalid email</b>

Send a valid email in the format: <code>name@domain.com</code>
        """
    },
    
    # Registrazione completata
    'registration_success': {
        'it': """
✅ <b>Registrazione completata!</b>

📧 Email: <code>{email}</code>
🆔 Chat ID: <code>{chat_id}</code>

Ora riceverai notifiche automatiche su:
• 📦 Spedizioni in entrata ricevute
• 📤 Spedizioni in uscita create/spedite/chiuse
• 🛒 Nuovi ordini
• 📋 Altri aggiornamenti importanti

🔔 Le notifiche sono <b>attive</b>. Usa /help per vedere altri comandi.
        """,
        'en': """
✅ <b>Registration completed!</b>

📧 Email: <code>{email}</code>
🆔 Chat ID: <code>{chat_id}</code>

You will now receive automatic notifications about:
• 📦 Inbound shipments received
• 📤 Outbound shipments created/shipped/closed
• 🛒 New orders
• 📋 Other important updates

🔔 Notifications are <b>active</b>. Use /help to see other commands.
        """
    },
    
    # Messaggio di test dopo registrazione
    'registration_test': {
        'it': """
🔧 <b>Messaggio di test</b>

Se ricevi questo messaggio, la configurazione è avvenuta con successo! 🎉

Da ora in poi riceverai qui tutte le notifiche relative ai tuoi ordini e spedizioni.
        """,
        'en': """
🔧 <b>Test message</b>

If you receive this message, the configuration was successful! 🎉

From now on, you will receive all notifications about your orders and shipments here.
        """
    },
    
    # Errore registrazione - email non trovata
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
    },
    
    # Errore registrazione generico
    'registration_error': {
        'it': """
❌ <b>Errore nella registrazione</b>

{message}

💡 <b>Suggerimenti:</b>
• Verifica di aver scritto correttamente l'email
• Contatta il supporto se il problema persiste
        """,
        'en': """
❌ <b>Registration error</b>

{message}

💡 <b>Suggestions:</b>
• Check that you have typed the email correctly
• Contact support if the problem persists
        """
    },
    
    # Test comando
    'test_success': {
        'it': """
✅ <b>Test di connessione riuscito!</b>

👤 <b>Utente:</b> {full_name}
📧 <b>Email:</b> {email}
🆔 <b>Chat ID:</b> {chat_id}
📊 <b>Notifiche inviate:</b> {notifications_sent}
📅 <b>Registrato il:</b> {registration_date}

🔔 Le notifiche sono <b>attive</b> e funzionanti!
        """,
        'en': """
✅ <b>Connection test successful!</b>

👤 <b>User:</b> {full_name}
📧 <b>Email:</b> {email}
🆔 <b>Chat ID:</b> {chat_id}
📊 <b>Notifications sent:</b> {notifications_sent}
📅 <b>Registered on:</b> {registration_date}

🔔 Notifications are <b>active</b> and working!
        """
    },
    
    # Test comando - utente non registrato
    'test_not_registered': {
        'it': """
❌ <b>Utente non registrato</b>

Per utilizzare questo bot devi prima registrarti inviando la tua email del Prep Center.

Esempio: <code>mario.rossi@example.com</code>

Usa /start per le istruzioni complete.
        """,
        'en': """
❌ <b>User not registered</b>

To use this bot you must first register by sending your Prep Center email.

Example: <code>mario.rossi@example.com</code>

Use /start for complete instructions.
        """
    },
    
    # Status comando
    'status': {
        'it': """
📊 <b>Stato della tua registrazione</b>

✅ <b>Stato:</b> Registrato e attivo
👤 <b>Nome:</b> {full_name}
📧 <b>Email:</b> {email}
🆔 <b>Chat ID:</b> {chat_id}
📅 <b>Registrato il:</b> {registration_date}
📊 <b>Notifiche ricevute:</b> {notifications_sent}
{last_notification}
🔔 <b>Notifiche:</b> Attive

<b>Eventi monitorati:</b>
• 📦 Spedizioni in entrata (create/ricevute/spedite)
• 📤 Spedizioni in uscita (create/spedite/chiuse) 
• 🛒 Ordini (creati/spediti)

Usa /test per inviare una notifica di prova.
        """,
        'en': """
📊 <b>Your registration status</b>

✅ <b>Status:</b> Registered and active
👤 <b>Name:</b> {full_name}
📧 <b>Email:</b> {email}
🆔 <b>Chat ID:</b> {chat_id}
📅 <b>Registered on:</b> {registration_date}
📊 <b>Notifications received:</b> {notifications_sent}
{last_notification}
🔔 <b>Notifications:</b> Active

<b>Monitored events:</b>
• 📦 Inbound shipments (created/received/shipped)
• 📤 Outbound shipments (created/shipped/closed) 
• 🛒 Orders (created/shipped)

Use /test to send a test notification.
        """
    },
    
    # Status comando - utente non registrato
    'status_not_registered': {
        'it': """
❌ <b>Utente non registrato</b>

Non risulti registrato nel sistema di notifiche.

📧 <b>Per registrarti:</b>
Invia la tua email del Prep Center (es: mario.rossi@example.com)

ℹ️ Usa /start per le istruzioni complete.
        """,
        'en': """
❌ <b>User not registered</b>

You are not registered in the notification system.

📧 <b>To register:</b>
Send your Prep Center email (ex: mario.rossi@example.com)

ℹ️ Use /start for complete instructions.
        """
    },
    
    # Comando non riconosciuto
    'unknown_command': {
        'it': """
❓ <b>Comando non riconosciuto</b>

Se vuoi registrarti, invia la tua email del Prep Center.
Se hai bisogno di aiuto, usa il comando /help.

<b>Comandi disponibili:</b>
• /help - Aiuto
• /test - Test connessione
• /status - Stato registrazione
• /start - Riavvia bot
• /language - Cambia lingua
        """,
        'en': """
❓ <b>Command not recognized</b>

If you want to register, send your Prep Center email.
If you need help, use the /help command.

<b>Available commands:</b>
• /help - Help
• /test - Connection test
• /status - Registration status
• /start - Restart bot
• /language - Change language
        """
    },
    
    # Errore del sistema
    'system_error': {
        'it': """
❌ <b>Errore del sistema</b>

Si è verificato un errore durante la registrazione. Riprova più tardi o contatta il supporto.
        """,
        'en': """
❌ <b>System error</b>

An error occurred during registration. Try again later or contact support.
        """
    },
    
    # Ultima notifica per status
    'last_notification': {
        'it': "📬 <b>Ultima notifica:</b> {date}\n",
        'en': "📬 <b>Last notification:</b> {date}\n"
    },
    
    'no_notifications': {
        'it': "📬 <b>Ultima notifica:</b> Nessuna notifica ricevuta ancora\n",
        'en': "📬 <b>Last notification:</b> No notifications received yet\n"
    },
    
    # Scelta lingua non valida
    'invalid_language_choice': {
        'text': "❌ Scelta non valida / Invalid choice\n\nScegli la lingua / Choose your language:\n• Scrivi \"i\" per Italiano\n• Type \"e\" for English"
    },
    
    # Comando language
    'language_command': {
        'it': """
🌍 <b>Cambia lingua</b>

Scegli la tua lingua:
• Scrivi <b>"i"</b> per Italiano
• Type <b>"e"</b> for English
        """,
        'en': """
🌍 <b>Change language</b>

Choose your language:
• Type <b>"e"</b> for English
• Scrivi <b>"i"</b> per Italiano
        """
    },
    
    # Notifiche spedizioni
    'notifications': {
        'inbound_shipment.created': {
            'it': 'Creata spedizione in entrata',
            'en': 'New inbound shipment created'
        },
        'inbound_shipment.received': {
            'it': 'Verificata spedizione in entrata',
            'en': 'Inbound shipment received'
        },
        'inbound_shipment.shipped': {
            'it': 'Arrivata spedizione in entrata',
            'en': 'Inbound shipment in transit'
        },
        'outbound_shipment.created': {
            'it': 'Creata spedizione in uscita',
            'en': 'New outbound shipment created'
        },
        'outbound_shipment.shipped': {
            'it': 'Spedizione in uscita spedita',
            'en': 'Outbound shipment shipped'
        },
        'outbound_shipment.closed': {
            'it': 'Pronta spedizione in uscita',
            'en': 'Outbound shipment completed'
        },
        'order.created': {
            'it': 'Nuovo ordine creato',
            'en': 'New order created'
        },
        'order.shipped': {
            'it': 'Ordine spedito',
            'en': 'Order shipped'
        }
    },
    
    # Labels per campi notifiche
    'notification_labels': {
        'id': {
            'it': 'ID',
            'en': 'ID'
        },
        'name': {
            'it': 'Nome',
            'en': 'Name'
        },
        'tracking': {
            'it': 'Tracking',
            'en': 'Tracking'
        },
        'carrier': {
            'it': 'Corriere',
            'en': 'Carrier'
        },
        'notes': {
            'it': 'Note',
            'en': 'Notes'
        },
        'products_count': {
            'it': '#prodotti',
            'en': '#products'
        },
        'default_title': {
            'it': 'Aggiornamento spedizione',
            'en': 'Shipment update'
        }
    },
    
    # Messaggi per admin
    'admin_new_message': {
        'it': "Nuovo messaggio Cliente {alias}",
        'en': "New message from Customer {alias}"
    },
    'admin_sender_label': {
        'it': "Da:",
        'en': "From:"
    },
    'admin_reply_instructions': {
        'it': "Rispondi normalmente o usa @{alias}",
        'en': "Reply normally or use @{alias}"
    },
    'admin_reply_context': {
        'it': "In risposta a:",
        'en': "In reply to:"
    }
}

def get_text(key, lang='it', subkey=None, **kwargs):
    """
    Ottiene il testo tradotto per una chiave e lingua specifica.
    
    Args:
        key: Chiave del messaggio
        lang: Codice lingua ('it' o 'en')
        subkey: Sottochiave per traduzioni annidate (opzionale)
        **kwargs: Parametri per formattare il messaggio
        
    Returns:
        str: Testo tradotto e formattato
    """
    if key not in TRANSLATIONS:
        return f"[MISSING TRANSLATION: {key}]"
    
    translation = TRANSLATIONS[key]
    
    # Gestisci traduzioni annidate (per notifiche)
    if subkey and isinstance(translation, dict) and subkey in translation:
        nested_translation = translation[subkey]
        if isinstance(nested_translation, dict):
            text = nested_translation.get(lang, nested_translation.get('it', f"[MISSING: {key}.{subkey}:{lang}]"))
        else:
            text = nested_translation
    # Per messaggi bilingue (solo benvenuto)
    elif isinstance(translation, dict) and 'text' in translation:
        text = translation['text']
    elif isinstance(translation, dict):
        # Prova la lingua richiesta, fallback su italiano
        text = translation.get(lang, translation.get('it', f"[MISSING: {key}:{lang}]"))
    else:
        # Testo semplice
        text = translation
    
    # Formatta con i parametri forniti
    try:
        return text.format(**kwargs)
    except KeyError as e:
        return f"[FORMAT ERROR in {key}: missing {e}]"

def get_user_language(chat_id):
    """
    Ottiene la lingua dell'utente dal database.
    
    Args:
        chat_id: ID della chat Telegram
        
    Returns:
        str: Codice lingua ('it' o 'en'), default 'it'
    """
    try:
        from .models import TelegramNotification
        user = TelegramNotification.objects.filter(chat_id=chat_id, is_active=True).first()
        if user and user.language_code:
            return user.language_code
    except:
        pass
    return 'it'  # Default italiano

def set_user_language(chat_id, language_code):
    """
    Imposta la lingua dell'utente nel database.
    
    Args:
        chat_id: ID della chat Telegram
        language_code: Codice lingua ('it' o 'en')
        
    Returns:
        bool: True se aggiornato con successo
    """
    try:
        from .models import TelegramNotification
        users = TelegramNotification.objects.filter(chat_id=chat_id)
        if users.exists():
            users.update(language_code=language_code)
            return True
        else:
            # Utente non ancora registrato, memorizziamo temporaneamente
            # Sarà impostato durante la registrazione
            return False
    except:
        return False 