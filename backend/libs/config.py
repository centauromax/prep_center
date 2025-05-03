"""
Configurazione per le librerie condivise.

Per configurare le API di Prep Business, imposta le seguenti variabili d'ambiente:

1. PREP_BUSINESS_API_URL - URL base dell'API (es. https://api.prepbusiness.com/api/v1)
2. PREP_BUSINESS_API_KEY - La tua chiave API per Prep Business
3. PREP_BUSINESS_API_TIMEOUT - Timeout per le richieste API in secondi (opzionale)
4. PREP_BUSINESS_MAX_RETRIES - Numero massimo di tentativi in caso di errore (opzionale)
5. PREP_BUSINESS_RETRY_BACKOFF - Fattore di attesa tra i tentativi (opzionale)

Puoi impostare queste variabili in uno dei seguenti modi:
- Variabili d'ambiente del sistema
- Nel file .env (con python-dotenv)
- Tramite il pannello di amministrazione (modello PrepBusinessConfig)
- Direttamente in questo file (solo per sviluppo/test)
"""
import os
import logging

# Configura il logger senza dipendere da django.conf
logger = logging.getLogger("prep_business")

# API settings per Prep Business - leggi solo da variabili d'ambiente per evitare problemi all'avvio
PREP_BUSINESS_API_URL = os.getenv('PREP_BUSINESS_API_URL', 'https://dashboard.fbaprepcenteritaly.com/api')
PREP_BUSINESS_API_KEY = os.getenv('PREP_BUSINESS_API_KEY', '')
PREP_BUSINESS_API_TIMEOUT = int(os.getenv('PREP_BUSINESS_API_TIMEOUT', '30'))

# Impostazioni di retry
PREP_BUSINESS_MAX_RETRIES = int(os.getenv('PREP_BUSINESS_MAX_RETRIES', '3'))
PREP_BUSINESS_RETRY_BACKOFF = float(os.getenv('PREP_BUSINESS_RETRY_BACKOFF', '0.5'))

# Headers predefiniti
DEFAULT_HEADERS = {
    'Authorization': f'Bearer {PREP_BUSINESS_API_KEY}',
    'Content-Type': 'application/json',
    'Accept': 'application/json',
} 