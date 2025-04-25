import requests
class PrepBusinessAPI:
    BASE_URL = "https://your-prepbusiness-domain/api"
    def __init__(self, api_key):
        self.headers = {"Authorization": f"Bearer {api_key}"}
    def get_open_inbound_shipments(self):
        response = requests.get(f"{self.BASE_URL}/inbound-shipments/open", headers=self.headers)
        return response.json()
