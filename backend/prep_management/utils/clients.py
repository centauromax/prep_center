from libs.prepbusiness.client import PrepBusinessClient
from libs.config import PREP_BUSINESS_API_KEY, PREP_BUSINESS_API_URL

def get_client():
    # Estrai il dominio dall'URL API
    domain = PREP_BUSINESS_API_URL.replace('https://', '').replace('http://', '').split('/')[0]
    return PrepBusinessClient(
        api_key=PREP_BUSINESS_API_KEY,
        company_domain=domain
    ) 