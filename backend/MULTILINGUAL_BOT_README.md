# Bot Telegram Multilingua - FBA Prep Center Italy

## 🌍 Funzionalità Implementate

Il bot Telegram ora supporta **Italiano** e **Inglese** con selezione automatica della lingua preferita dall'utente.

### ✨ Caratteristiche Principali

1. **Messaggio di Benvenuto Bilingue**
   - Al comando `/start`, il bot mostra un messaggio in entrambe le lingue
   - L'utente può scegliere tra "i" (Italiano) e "e" (English)

2. **Memorizzazione Lingua Utente**
   - La lingua scelta viene salvata nel database (`language_code` nel modello `TelegramNotification`)
   - Tutti i messaggi successivi vengono inviati nella lingua preferita

3. **Comandi Multilingua**
   - `/start` - Messaggio di benvenuto bilingue
   - `/help` - Aiuto nella lingua dell'utente
   - `/test` - Test connessione nella lingua dell'utente
   - `/status` - Stato registrazione nella lingua dell'utente
   - `/language` - Permette di cambiare lingua in qualsiasi momento

4. **Gestione Errori Localizzata**
   - Messaggi di errore (email non valida, utente non registrato, ecc.) nella lingua dell'utente
   - Fallback automatico all'italiano se la lingua non è disponibile

### 🔧 Implementazione Tecnica

#### File Principali

1. **`translations.py`** - Sistema di traduzioni centralizzato
   - Dizionario `TRANSLATIONS` con tutte le traduzioni
   - Funzione `get_text(key, lang, **kwargs)` per ottenere testi tradotti
   - Funzioni `get_user_language()` e `set_user_language()` per gestire le preferenze

2. **`views.py`** - Logica del webhook aggiornata
   - `handle_language_selection()` - Gestisce la scelta della lingua
   - `handle_language_command()` - Comando per cambiare lingua
   - Tutte le funzioni aggiornate per usare le traduzioni

3. **`services.py`** - Servizi aggiornati
   - `register_telegram_user()` aggiornato per gestire utenti temporanei con lingua

#### Flusso di Registrazione

```
1. Utente: /start
2. Bot: Messaggio bilingue con scelta lingua
3. Utente: "i" o "e"
4. Bot: Conferma lingua + richiesta email
5. Utente: email@example.com
6. Bot: Verifica email + registrazione
7. Bot: Conferma registrazione + messaggio test
```

#### Gestione Utenti Temporanei

- Quando un utente sceglie la lingua ma non si è ancora registrato, viene creato un record temporaneo
- Email temporanea: `temp_{chat_id}@temp.com`
- `is_active = False` finché non completa la registrazione
- Durante la registrazione vera, il record viene aggiornato con l'email reale

### 📝 Traduzioni Disponibili

#### Messaggi Principali
- `welcome_bilingual` - Messaggio di benvenuto bilingue
- `language_selected` - Conferma selezione lingua
- `help` - Messaggio di aiuto
- `registration_success` - Registrazione completata
- `registration_test` - Messaggio di test post-registrazione

#### Messaggi di Errore
- `invalid_email` - Email non valida
- `registration_error` - Errore nella registrazione
- `system_error` - Errore del sistema
- `test_not_registered` - Utente non registrato (comando test)
- `status_not_registered` - Utente non registrato (comando status)
- `unknown_command` - Comando non riconosciuto
- `invalid_language_choice` - Scelta lingua non valida

#### Comandi
- `language_command` - Messaggio per cambiare lingua
- `last_notification` / `no_notifications` - Info ultima notifica

### 🧪 Test

Eseguire il test delle traduzioni:
```bash
python simple_test_translations.py
```

Il test verifica:
- ✅ Funzionamento delle traduzioni
- ✅ Gestione parametri dinamici
- ✅ Fallback per chiavi mancanti
- ✅ Simulazione flusso completo utente

### 🚀 Utilizzo

#### Per l'Utente
1. Cerca il bot su Telegram
2. Invia `/start`
3. Scegli lingua: "i" per Italiano, "e" per English
4. Inserisci la tua email del Prep Center
5. Inizia a ricevere notifiche nella tua lingua!

#### Comandi Disponibili
- `/start` - Riavvia il bot (mostra selezione lingua)
- `/help` - Mostra aiuto nella tua lingua
- `/test` - Testa la connessione
- `/status` - Mostra il tuo stato di registrazione
- `/language` - Cambia lingua

### 🔄 Cambio Lingua

Gli utenti possono cambiare lingua in qualsiasi momento:
1. Comando `/language`
2. Scegliere nuova lingua: "i" o "e"
3. Tutti i messaggi successivi saranno nella nuova lingua

### 📊 Statistiche

Il sistema tiene traccia di:
- Lingua preferita di ogni utente
- Data di registrazione
- Numero di notifiche inviate
- Ultima notifica ricevuta

### 🛠️ Manutenzione

#### Aggiungere Nuove Traduzioni
1. Aggiungere la chiave in `TRANSLATIONS` in `translations.py`
2. Fornire traduzioni per 'it' e 'en'
3. Usare `get_text('nuova_chiave', lang=user_lang)` nel codice

#### Aggiungere Nuove Lingue
1. Aggiungere il codice lingua (es. 'fr', 'de') nelle traduzioni
2. Aggiornare `language_map` in `handle_language_selection()`
3. Aggiornare il messaggio di benvenuto bilingue

### 🔒 Sicurezza

- La validazione email rimane invariata
- Solo email autorizzate nel Prep Center possono registrarsi
- La lingua è solo una preferenza di visualizzazione
- Nessun impatto sulla sicurezza del sistema

### 📈 Benefici

1. **Esperienza Utente Migliorata**
   - Interfaccia nella lingua preferita
   - Messaggi più chiari e comprensibili

2. **Accessibilità Internazionale**
   - Supporto clienti internazionali
   - Espansione del servizio

3. **Professionalità**
   - Bot più professionale e user-friendly
   - Riduzione errori di comprensione

4. **Scalabilità**
   - Facile aggiunta di nuove lingue
   - Sistema modulare e mantenibile 