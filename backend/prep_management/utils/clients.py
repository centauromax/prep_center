from libs.prepbusiness.client import PrepBusinessClient
from libs.config import PREP_BUSINESS_API_KEY, PREP_BUSINESS_API_URL

def get_client():
    company_domain = PREP_BUSINESS_API_URL.split('//')[-1].split('/')[0]
    return PrepBusinessClient(
        api_key=PREP_BUSINESS_API_KEY,
        company_domain=company_domain
    ) 