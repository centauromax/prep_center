"""
PrepBusiness - Libreria client per l'API di Prep Business.
"""

from .client import PrepBusinessClient
from .models import (
    PrepBusinessError, AuthenticationError, PaginatedResponse,
    Webhook, WebhooksResponse, WebhookResponse, DeleteWebhookResponse,
    WebhookTypes, InvoiceWebhookTypes, InboundShipmentWebhookTypes, 
    OutboundShipmentWebhookTypes, OrderWebhookTypes
)
from .search import SearchQuery

__version__ = '1.0.0'

__all__ = [
    'PrepBusinessClient',
    'PrepBusinessError',
    'AuthenticationError',
    'PaginatedResponse',
    'Webhook',
    'WebhooksResponse',
    'WebhookResponse',
    'DeleteWebhookResponse',
    'WebhookTypes',
    'InvoiceWebhookTypes',
    'InboundShipmentWebhookTypes',
    'OutboundShipmentWebhookTypes',
    'OrderWebhookTypes',
    'SearchQuery',
]
