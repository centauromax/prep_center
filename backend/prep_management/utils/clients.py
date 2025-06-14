from libs.prepbusiness.client import PrepBusinessClient
from libs.config import PREP_BUSINESS_API_KEY, PREP_BUSINESS_API_URL

def get_client():
    return PrepBusinessClient(
        api_url=PREP_BUSINESS_API_URL,
        api_key=PREP_BUSINESS_API_KEY
    ) 