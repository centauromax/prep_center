from dataclasses import dataclass
from typing import Optional

@dataclass
class Config:
    """Configuration class for PrepBusiness client."""
    api_key: str
    client_id: str
    default_merchant_id: Optional[str] = None
    base_url: str = "https://api.prepbusiness.com"
    timeout: int = 30
    max_retries: int = 3 