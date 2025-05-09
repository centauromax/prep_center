import requests
from libs.prepbusiness.client import PrepBusinessClient
from libs.config import PREP_BUSINESS_API_URL

class PrepBusinessAPI:
    """
    Wrapper per le API di Prep Business.
    NOTA: Questa classe è mantenuta per retrocompatibilità.
    Si consiglia di utilizzare direttamente PrepBusinessClient per nuove implementazioni.
    """
    def __init__(self, api_key):
        """Inizializza il client PrepBusiness"""
        # Manteniamo self.headers per retrocompatibilità
        self.headers = {"Authorization": f"Bearer {api_key}"}
        
        # Estraiamo il dominio dall'URL API
        company_domain = PREP_BUSINESS_API_URL.split('//')[-1].split('/')[0]
        
        # Inizializza il client PrepBusiness
        self.client = PrepBusinessClient(
            api_key=api_key,
            company_domain=company_domain
        )
    
    def get_open_inbound_shipments(self):
        """
        Recupera le spedizioni in entrata aperte utilizzando PrepBusinessClient.
        
        Returns:
            Lista di spedizioni in entrata aperte
        """
        try:
            # Utilizziamo il client PrepBusiness invece di requests diretti
            response = self.client.get_inbound_shipments()
            
            # Filtriamo solo le spedizioni aperte
            open_shipments = [
                shipment for shipment in response.data
                if getattr(shipment, 'status', None) == 'open'
            ]
            
            # Convertiamo in dict per mantenere la compatibilità con l'implementazione precedente
            return [
                {
                    'id': shipment.id,
                    'name': shipment.name,
                    'status': shipment.status,
                    'created_at': shipment.created_at.isoformat() if hasattr(shipment.created_at, 'isoformat') else shipment.created_at,
                    # Aggiungi altri campi necessari
                }
                for shipment in open_shipments
            ]
        except Exception as e:
            # In caso di errore, restituisci un elenco vuoto
            return []
