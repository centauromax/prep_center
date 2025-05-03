"""
Configurazione per le librerie condivise.
"""
import os
from django.conf import settings

# API settings per Prep Business
PREP_BUSINESS_API_URL = os.getenv('PREP_BUSINESS_API_URL', 'https://api.prepbusiness.com/api/v1')
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