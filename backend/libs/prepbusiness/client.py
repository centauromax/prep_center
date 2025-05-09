from typing import Optional, Dict, Any, List, Union, Tuple, TypeVar, Generic
from datetime import date, datetime
import requests
import json
import os
from pydantic import BaseModel, Field
from requests_toolbelt.multipart.encoder import MultipartEncoder
from .search import SearchQuery
from .models import (
    PrepBusinessError, AuthenticationError, PaginatedResponse,
    Channel, Listing, ListingResponse,
    Charge, ChargesResponse, ChargeDetailsResponse, InvoicesResponse, CreateInvoiceResponse,
    InventoryResponse, InventoryItemResponse, InventorySearchResponse, InboundShipmentsResponse,
    InboundShipmentResponse, Carrier, CreateInboundShipmentResponse, UpdateInboundShipmentResponse,
    SubmitInboundShipmentResponse, ReceiveInboundShipmentResponse, BatchArchiveInboundShipmentsResponse,
    RemoveItemFromShipmentResponse, AddItemToShipmentResponse, ShipmentItemsResponse,
    ExpectedItemUpdate, ActualItemUpdate, UpdateShipmentItemResponse, OutboundShipmentsResponse,
    OutboundShipmentResponse, CreateOutboundShipmentResponse, AddOutboundShipmentAttachmentResponse,
    AddOutboundShipmentItemResponse, OutboundShipmentItemsResponse,
    UpdateOutboundShipmentItemResponse, ItemGroupConfigurationUpdate, OutboundShipment, OutboundShipmentItem,
    OutboundShipmentItemUpdate, OrdersResponse, OrderResponse, UploadOrdersResponse, OrderUpload,
    Service, ServicesResponse, WarehousesResponse, AdjustmentReason, CreateAdjustmentResponse,
    Merchant, MerchantsResponse, Webhook, WebhooksResponse, WebhookResponse, DeleteWebhookResponse,
    WebhookTypes, InvoiceWebhookTypes, InboundShipmentWebhookTypes, OutboundShipmentWebhookTypes, OrderWebhookTypes
)

T = TypeVar('T')

class PrepBusinessConfig(BaseModel):
    """Configuration for the PrepBusiness client."""
    api_key: str = Field(..., description="API key for authentication")
    company_domain: str = Field(..., description="Company domain (e.g. portal.yourcompany.com)")
    timeout: int = Field(default=30, description="Request timeout in seconds")
    use_query_auth: bool = Field(
        default=False,
        description="Whether to use query parameter authentication instead of Bearer token"
    )
    default_merchant_id: Optional[int] = Field(
        default=None,
        description="Default merchant ID to use for requests"
    )
    default_per_page: int = Field(
        default=50,
        description="Default number of items per page for paginated requests"
    )

class PrepBusinessClient:
    """Client for interacting with the PrepBusiness API."""
    
    def __init__(
        self,
        api_key: str,
        company_domain: str,
        timeout: Optional[int] = None,
        use_query_auth: bool = False,
        default_merchant_id: Optional[int] = None,
        default_per_page: int = 50
    ) -> None:
        """Initialize the PrepBusiness client.
        
        Args:
            api_key: Your PrepBusiness API key
            company_domain: Your company domain (e.g. portal.yourcompany.com)
            timeout: Optional request timeout in seconds
            use_query_auth: Whether to use query parameter authentication instead of Bearer token
            default_merchant_id: Optional default merchant ID to use for requests
            default_per_page: Default number of items per page for paginated requests
        """
        self.config = PrepBusinessConfig(
            api_key=api_key,
            company_domain=company_domain,
            timeout=timeout or 30,
            use_query_auth=use_query_auth,
            default_merchant_id=default_merchant_id,
            default_per_page=default_per_page
        )
        self._session = requests.Session()
        self._update_headers()

    def _update_headers(self, merchant_id: Optional[int] = None) -> None:
        """Update session headers with current configuration.
        
        Args:
            merchant_id: Optional merchant ID to use for this request
        """
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Add authentication header if not using query auth
        if not self.config.use_query_auth:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
            
        # Add merchant header if specified
        merchant_id = merchant_id or self.config.default_merchant_id
        if merchant_id is not None:
            headers["X-Selected-Client-Id"] = str(merchant_id)
            
        self._session.headers.update(headers)

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        merchant_id: Optional[int] = None,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
        search_query: Optional[SearchQuery] = None
    ) -> Dict[str, Any]:
        """Make an HTTP request to the PrepBusiness API.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            params: Optional query parameters
            json: Optional JSON body
            data: Optional form-encoded data
            files: Optional files to upload
            headers: Optional custom headers
            merchant_id: Optional merchant ID to use for this request
            page: Optional page number for paginated requests
            per_page: Optional number of items per page
            search_query: Optional search query to filter results
            
        Returns:
            Dict containing the API response
            
        Raises:
            AuthenticationError: If authentication fails
            PrepBusinessError: For other API errors with error details
        """
        url = f"https://{self.config.company_domain}/api/{endpoint.lstrip('/')}"
        
        # Add API key to query params if using query auth
        request_params = params or {}
        if self.config.use_query_auth:
            request_params["api_token"] = self.config.api_key
            
        # Add pagination parameters if specified
        if page is not None:
            request_params["page"] = page
        if per_page is not None:
            request_params["per_page"] = per_page
            
        # Add search query if specified
        if search_query is not None:
            query_str = search_query.build()
            if query_str:
                request_params["q"] = query_str
            
        # Update headers with merchant ID if specified
        if merchant_id is not None:
            self._update_headers(merchant_id)
            
        # Merge custom headers with session headers
        request_headers = self._session.headers.copy()
        if headers:
            request_headers.update(headers)
        # Rimuovi Content-Type se files è presente
        if files and "Content-Type" in request_headers:
            del request_headers["Content-Type"]
        
        try:
            response = self._session.request(
                method=method,
                url=url,
                params=request_params,
                json=json,
                data=data,
                files=files,
                headers=request_headers,
                timeout=self.config.timeout
            )
            
            # Check for authentication errors
            if response.status_code == 401:
                raise AuthenticationError("Invalid API key or authentication failed")
                
            # For other errors, try to get detailed error message
            if response.status_code >= 400:
                error_msg = "API request failed"
                try:
                    error_data = response.json()
                    if isinstance(error_data, dict):
                        error_msg = error_data.get('message', error_msg)
                        if 'errors' in error_data:
                            error_msg += f"\nDetails: {error_data['errors']}"
                except ValueError:
                    error_msg = response.text or error_msg
                
                raise PrepBusinessError(f"{error_msg} (Status: {response.status_code})")
                
            return response.json()
        except requests.exceptions.RequestException as e:
            if isinstance(e, AuthenticationError):
                raise
            raise PrepBusinessError(f"API request failed: {str(e)}") from e

    def get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        merchant_id: Optional[int] = None,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
        search_query: Optional[SearchQuery] = None
    ) -> Dict[str, Any]:
        """Make a GET request to the PrepBusiness API.
        
        Args:
            endpoint: API endpoint path
            params: Optional query parameters
            merchant_id: Optional merchant ID to use for this request
            page: Optional page number for paginated requests
            per_page: Optional number of items per page
            search_query: Optional search query to filter results
            
        Returns:
            Dict containing the API response
            
        Raises:
            AuthenticationError: If authentication fails
            PrepBusinessError: For other API errors
        """
        return self._request(
            "GET",
            endpoint,
            params=params,
            merchant_id=merchant_id,
            page=page,
            per_page=per_page,
            search_query=search_query
        )

    def get_paginated(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        merchant_id: Optional[int] = None,
        page: int = 1,
        per_page: Optional[int] = None,
        response_model: Optional[type] = None,
        search_query: Optional[SearchQuery] = None
    ) -> PaginatedResponse:
        """Make a paginated GET request to the PrepBusiness API.
        
        Args:
            endpoint: API endpoint path
            params: Optional query parameters
            merchant_id: Optional merchant ID to use for this request
            page: Page number to retrieve (default: 1)
            per_page: Optional number of items per page
            response_model: Optional Pydantic model to validate response data
            search_query: Optional search query to filter results
            
        Returns:
            PaginatedResponse containing the paginated data
            
        Raises:
            AuthenticationError: If authentication fails
            PrepBusinessError: For other API errors
        """
        response = self.get(
            endpoint,
            params=params,
            merchant_id=merchant_id,
            page=page,
            per_page=per_page or self.config.default_per_page,
            search_query=search_query
        )
        
        # Se la risposta contiene direttamente i dati (senza paginazione)
        if "channels" in response:
            data = response["channels"]
            # Crea una risposta paginata con i dati
            paginated_response = {
                "data": data,
                "current_page": 1,
                "from": 1,
                "to": len(data),
                "total": len(data),
                "last_page": 1,
                "per_page": len(data)
            }
            response = paginated_response
        
        # If response_model is provided, validate the data items
        if response_model is not None:
            response["data"] = [response_model(**item) for item in response["data"]]
            
        return PaginatedResponse(**response)

    def post(
        self,
        endpoint: str,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        merchant_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Make a POST request to the PrepBusiness API.
        
        Args:
            endpoint: API endpoint path
            json: Optional JSON body
            data: Optional form-encoded data
            merchant_id: Optional merchant ID to use for this request
            
        Returns:
            Dict containing the API response
            
        Raises:
            AuthenticationError: If authentication fails
            PrepBusinessError: For other API errors
        """
        return self._request("POST", endpoint, json=json, data=data, merchant_id=merchant_id)

    def get_channels(
        self,
        merchant_id: Optional[int] = None,
        page: int = 1,
        per_page: Optional[int] = None,
        search_query: Optional[SearchQuery] = None
    ) -> PaginatedResponse[Channel]:
        """Get a list of channels for the merchant.
        
        Args:
            merchant_id: Optional merchant ID to use for this request
            page: Page number to retrieve (default: 1)
            per_page: Optional number of items per page
            search_query: Optional search query to filter results
            
        Returns:
            PaginatedResponse containing the list of channels
            
        Raises:
            AuthenticationError: If authentication fails
            PrepBusinessError: For other API errors
        """
        response = self.get_paginated(
            "channels",
            merchant_id=merchant_id,
            page=page,
            per_page=per_page,
            response_model=Channel,
            search_query=search_query
        )
        
        # La risposta contiene i canali nel campo "channels" invece di "data"
        if "channels" in response.data:
            response.data = response.data["channels"]
            
        return response

    def get_channel_listings(
        self,
        channel_id: int,
        page: int = 1,
        per_page: int = 100,
        search: Optional[str] = None
    ) -> ListingResponse:
        """
        Get listings for a specific channel with pagination and optional search.

        Args:
            channel_id: The ID of the channel
            page: Page number (default: 1)
            per_page: Number of items per page (default: 100, max: 100)
            search: Optional search query using the search language

        Returns:
            ListingResponse containing the listings and pagination info

        Raises:
            PrepBusinessError: If the API request fails
        """
        params = {
            "page": page,
            "per_page": min(per_page, 100)  # API limit is 100 items per page
        }
        
        if search:
            params["search"] = search
            
        response = self._request(
            "GET",
            f"/channels/{channel_id}/listings",
            params=params
        )
        
        return ListingResponse(**response)

    def get_charges(
        self,
        merchant_id: Optional[int] = None,
        page: int = 1,
        per_page: int = 100
    ) -> ChargesResponse:
        """
        Get charges for a merchant with pagination.

        Args:
            merchant_id: The ID of the merchant (required in header)
            page: Page number (default: 1)
            per_page: Number of items per page (default: 100, max: 100)

        Returns:
            ChargesResponse containing the charges and pagination info

        Raises:
            PrepBusinessError: If the API request fails
        """
        params = {
            "page": page,
            "per_page": min(per_page, 100)  # API limit is 100 items per page
        }
        
        response = self._request(
            "GET",
            "/billing/charges",
            params=params,
            merchant_id=merchant_id
        )
        
        return ChargesResponse.model_validate(response)

    def get_charge_details(self, charge_id: int) -> ChargeDetailsResponse:
        """
        Get detailed information about a specific charge.

        Args:
            charge_id: The ID of the charge to retrieve.

        Returns:
            ChargeDetailsResponse: Detailed information about the charge and its items.

        Raises:
            PrepBusinessError: If the API request fails.
        """
        response = self._request(
            "GET",
            f"/billing/charges/{charge_id}",
            merchant_id=self.config.default_merchant_id
        )
        return ChargeDetailsResponse.model_validate(response)

    def create_quick_adjustment(
        self,
        amount: float,
        description: str,
        merchant_id: Optional[int] = None
    ) -> ChargeDetailsResponse:
        """
        Create a quick adjustment on a client's account.

        Args:
            amount: The amount for the quick adjustment
            description: The description for the quick adjustment
            merchant_id: Optional merchant ID to use for this request

        Returns:
            ChargeDetailsResponse: Detailed information about the created charge

        Raises:
            PrepBusinessError: If the API request fails
        """
        response = self._request(
            "POST",
            "/billing/charges/quick-adjustment",
            json={
                "amount": amount,
                "description": description
            },
            merchant_id=merchant_id
        )
        return ChargeDetailsResponse.model_validate(response)

    def get_invoices(
        self,
        merchant_id: Optional[int] = None,
        page: int = 1,
        per_page: int = 100
    ) -> InvoicesResponse:
        """
        Get a list of invoices for a merchant.

        Args:
            merchant_id: Optional merchant ID to use for this request
            page: Page number (default: 1)
            per_page: Number of items per page (default: 100, max: 100)

        Returns:
            InvoicesResponse containing the list of invoices

        Raises:
            PrepBusinessError: If the API request fails
        """
        params = {
            "page": page,
            "per_page": min(per_page, 100)  # API limit is 100 items per page
        }
        
        response = self._request(
            "GET",
            "/billing/invoices",
            params=params,
            merchant_id=merchant_id
        )
        
        return InvoicesResponse.model_validate(response)

    def create_invoice(
        self,
        charge_ids: List[int],
        merchant_id: Optional[int] = None
    ) -> CreateInvoiceResponse:
        """
        Create a new invoice for a list of charges.

        Args:
            charge_ids: List of charge IDs to create an invoice for
            merchant_id: Optional merchant ID to use for this request

        Returns:
            CreateInvoiceResponse containing the created invoice details

        Raises:
            PrepBusinessError: If the API request fails
        """
        response = self._request(
            "POST",
            "/billing/invoices",
            json={"charge_ids": charge_ids},
            merchant_id=merchant_id
        )
        
        return CreateInvoiceResponse.model_validate(response)

    def get_inventory(
        self,
        merchant_id: Optional[int] = None,
        page: int = 1,
        per_page: int = 500,
        search_query: Optional[SearchQuery] = None
    ) -> InventoryResponse:
        """
        Get a list of all inventory items.

        Args:
            merchant_id: Optional merchant ID to use for this request
            page: Page number (default: 1)
            per_page: Number of items per page (default: 500, max: 500)
            search_query: Optional search query to filter results

        Returns:
            InventoryResponse containing the list of inventory items

        Raises:
            PrepBusinessError: If the API request fails
        """
        params = {
            "page": page,
            "per_page": min(per_page, 500)  # API limit is 500 items per page
        }
        
        if search_query:
            params["search"] = str(search_query)
            
        response = self._request(
            "GET",
            "/inventory",
            params=params,
            merchant_id=merchant_id
        )
        
        return InventoryResponse.model_validate(response)

    def get_inventory_item(
        self,
        item_id: int,
        merchant_id: Optional[int] = None
    ) -> InventoryItemResponse:
        """
        Get detailed information about a specific inventory item.

        Args:
            item_id: The ID of the inventory item to retrieve
            merchant_id: Optional merchant ID to use for this request

        Returns:
            InventoryItemResponse containing the detailed item information

        Raises:
            PrepBusinessError: If the API request fails
        """
        response = self._request(
            "GET",
            f"/inventory/{item_id}",
            merchant_id=merchant_id
        )
        
        return InventoryItemResponse.model_validate(response)

    def search_inventory(self, query: str) -> InventorySearchResponse:
        """Search for inventory items by title, SKU, or identifiers.

        The search will return up to 10 items matching the title or SKU,
        plus any items with matching identifiers.

        Args:
            query: The search query to match against title, SKU, or identifiers.

        Returns:
            InventorySearchResponse containing matching items.

        Raises:
            PrepBusinessError: If the API request fails.
        """
        response = self._request(
            "POST",
            "/inventory/search",
            json={"q": query}
        )
        return InventorySearchResponse.model_validate(response)

    def create_inventory_item(
        self,
        merchant_sku: str,
        title: str,
        condition: Optional[str] = None,
        condition_note: Optional[str] = None,
        asin: Optional[str] = None,
        merchant_id: Optional[int] = None
    ) -> InventoryItemResponse:
        """Create a new inventory item.

        Args:
            merchant_sku: The SKU for the item. Must be unique for the merchant.
                Min 3 characters, max 255 characters.
            title: The title for the item. Min 3 characters, max 255 characters.
            condition: Optional. The condition of the item (using Amazon's condition values).
            condition_note: Optional. Notes about the item's condition.
            asin: Optional. The Amazon ASIN for the item.
            merchant_id: Optional merchant ID to use for this request.

        Returns:
            InventoryItemResponse containing the created item details.

        Raises:
            PrepBusinessError: If the API request fails or validation fails.
        """
        data = {
            "merchant_sku": merchant_sku,
            "title": title
        }
        
        if condition is not None:
            data["condition"] = condition
        if condition_note is not None:
            data["condition_note"] = condition_note
        if asin is not None:
            data["asin"] = asin

        response = self._request(
            "POST",
            "/inventory",
            json=data,
            merchant_id=merchant_id
        )
        
        print("Raw API Response:", response)  # Debug print
        return InventoryItemResponse.model_validate(response)

    def update_inventory_item(
        self,
        item_id: int,
        length_mm: int,
        width_mm: int,
        height_mm: int,
        weight_gm: int,
        merchant_id: Optional[int] = None
    ) -> InventoryItemResponse:
        """Update an existing inventory item's dimensions and weight.

        Args:
            item_id: The ID of the item to update.
            length_mm: The length of the item in millimeters. Min 1, max 500000.
            width_mm: The width of the item in millimeters. Min 1, max 500000.
            height_mm: The height of the item in millimeters. Min 1, max 500000.
            weight_gm: The weight of the item in grams. Min 1, max 500000.
            merchant_id: Optional merchant ID to use for this request.

        Returns:
            InventoryItemResponse containing the updated item details.

        Raises:
            PrepBusinessError: If the API request fails or validation fails.
        """
        data = {
            "length_mm": length_mm,
            "width_mm": width_mm,
            "height_mm": height_mm,
            "weight_gm": weight_gm
        }

        response = self._request(
            "PUT",
            f"/inventory/{item_id}",
            json=data,
            merchant_id=merchant_id
        )
        
        print("Raw Update API Response:", response)  # Debug print
        return InventoryItemResponse.model_validate(response)

    def add_inventory_identifier(
        self,
        item_id: int,
        identifier: str,
        identifier_type: str,
        merchant_id: Optional[int] = None
    ) -> Dict[str, str]:
        """Add an identifier to an existing inventory item.

        Args:
            item_id: The ID of the item to add the identifier to.
            identifier: The identifier value. Must match the format for the given type:
                - UPC: 12 digits
                - EAN: 13 digits
                - FNSKU: 10 characters
                - ASIN: 10 characters
                - CUSTOM: 1-255 characters
            identifier_type: The type of identifier. Must be one of:
                UPC, EAN, FNSKU, ASIN, CUSTOM
            merchant_id: Optional merchant ID to use for this request.

        Returns:
            Dict containing the response message and the added identifier.

        Raises:
            PrepBusinessError: If the API request fails or validation fails.
        """
        data = {
            "identifier": identifier,
            "identifier_type": identifier_type
        }

        response = self._request(
            "POST",
            f"/inventory/{item_id}/identifier",
            json=data,
            merchant_id=merchant_id
        )
        
        return response

    def add_inventory_services(
        self,
        item_id: int,
        service_ids: List[int],
        merchant_id: Optional[int] = None
    ) -> Dict[str, str]:
        """Add services to an existing inventory item.

        Args:
            item_id: The ID of the item to add services to.
            service_ids: List of service IDs to add to the item.
            merchant_id: Optional merchant ID to use for this request.

        Returns:
            Dict containing the response message.

        Raises:
            PrepBusinessError: If the API request fails or validation fails.
        """
        data = {
            "item_id": item_id,
            "services": service_ids
        }

        response = self._request(
            "POST",
            "/inventory/services",
            json=data,
            merchant_id=merchant_id
        )
        
        return response

    def get_inbound_shipments(
        self,
        page: int = 1,
        per_page: int = 20,
        merchant_id: Optional[int] = None
    ) -> InboundShipmentsResponse:
        """Get a list of all inbound shipments with pagination.

        Args:
            page: Page number to retrieve (default: 1)
            per_page: Number of items per page (default: 20)
            merchant_id: Optional merchant ID to use for this request

        Returns:
            InboundShipmentsResponse containing the list of shipments and pagination info

        Raises:
            PrepBusinessError: If the API request fails
        """
        params = {
            "page": page,
            "per_page": per_page
        }
        
        response = self._request(
            "GET",
            "/shipments/inbound",
            params=params,
            merchant_id=merchant_id
        )
        
        return InboundShipmentsResponse.model_validate(response)

    def get_inbound_shipment(
        self,
        shipment_id: int,
        merchant_id: Optional[int] = None
    ) -> InboundShipmentResponse:
        """Get detailed information about a specific inbound shipment.

        Args:
            shipment_id: The ID of the shipment to retrieve
            merchant_id: Optional merchant ID to use for this request

        Returns:
            InboundShipmentResponse containing the detailed shipment information

        Raises:
            PrepBusinessError: If the API request fails
        """
        response = self._request(
            "GET",
            f"/shipments/inbound/{shipment_id}",
            merchant_id=merchant_id
        )
        
        return InboundShipmentResponse.model_validate(response)

    def create_inbound_shipment(
        self,
        name: str,
        warehouse_id: int,
        notes: Optional[str] = None,
        merchant_id: Optional[int] = None
    ) -> CreateInboundShipmentResponse:
        """Create a new inbound shipment.

        Args:
            name: The name of the shipment
            warehouse_id: The ID of the warehouse to send the shipment from
            notes: Optional notes about the shipment
            merchant_id: Optional merchant ID to use for this request

        Returns:
            CreateInboundShipmentResponse containing the created shipment ID

        Raises:
            PrepBusinessError: If the API request fails
        """
        data = {
            "name": name,
            "warehouse_id": warehouse_id
        }
        
        if notes is not None:
            data["notes"] = notes
            
        response = self._request(
            "POST",
            "/shipments/inbound",
            json=data,
            merchant_id=merchant_id
        )
        
        return CreateInboundShipmentResponse.model_validate(response)

    def update_inbound_shipment(
        self,
        shipment_id: int,
        name: Optional[str] = None,
        notes: Optional[str] = None,
        internal_notes: Optional[str] = None,
        merchant_id: Optional[int] = None
    ) -> UpdateInboundShipmentResponse:
        """Update an existing inbound shipment.

        Args:
            shipment_id: The ID of the shipment to update
            name: Optional new name for the shipment
            notes: Optional new notes about the shipment
            internal_notes: Optional new internal notes for warehouse/staff
            merchant_id: Optional merchant ID to use for this request

        Returns:
            UpdateInboundShipmentResponse containing the updated shipment details

        Raises:
            PrepBusinessError: If the API request fails
        """
        data = {}
        if name is not None:
            data["name"] = name
        if notes is not None:
            data["notes"] = notes
        if internal_notes is not None:
            data["internal_notes"] = internal_notes

        response = self._request(
            "PUT",
            f"/shipments/inbound/{shipment_id}",
            json=data,
            merchant_id=merchant_id
        )
        
        print("Raw API Response:", response)  # Debug print
        
        return UpdateInboundShipmentResponse.model_validate(response)

    def submit_inbound_shipment(
        self,
        shipment_id: int,
        tracking_numbers: Optional[List[str]] = None,
        carrier: Optional[Carrier] = None,
        merchant_id: Optional[int] = None
    ) -> SubmitInboundShipmentResponse:
        """Submit an inbound shipment with tracking numbers.

        Args:
            shipment_id: The ID of the shipment to submit
            tracking_numbers: Optional list of tracking numbers. Required unless carrier is NO_TRACKING
            carrier: Optional carrier for the shipment. Defaults to NO_TRACKING if not provided
            merchant_id: Optional merchant ID to use for this request

        Returns:
            SubmitInboundShipmentResponse containing the submission confirmation

        Raises:
            PrepBusinessError: If the API request fails
            ValueError: If neither tracking_numbers nor carrier is provided
        """
        if tracking_numbers is None and carrier is None:
            raise ValueError("Either tracking_numbers or carrier must be provided")
            
        data = {}
        if tracking_numbers is not None:
            data["tracking_numbers"] = tracking_numbers
        if carrier is not None:
            data["carrier"] = carrier.value

        response = self._request(
            "POST",
            f"/shipments/inbound/{shipment_id}/submit",
            json=data,
            merchant_id=merchant_id
        )
        
        return SubmitInboundShipmentResponse.model_validate(response)

    def receive_inbound_shipment(
        self,
        shipment_id: int,
        merchant_id: Optional[int] = None
    ) -> ReceiveInboundShipmentResponse:
        """Receive an inbound shipment, changing its status to received.

        Args:
            shipment_id: The ID of the shipment to receive
            merchant_id: Optional merchant ID to use for this request

        Returns:
            ReceiveInboundShipmentResponse containing the reception confirmation

        Raises:
            PrepBusinessError: If the API request fails
        """
        response = self._request(
            "POST",
            f"/shipments/inbound/{shipment_id}/receive",
            merchant_id=merchant_id
        )
        
        return ReceiveInboundShipmentResponse.model_validate(response)

    def batch_archive_inbound_shipments(
        self,
        shipment_ids: List[int],
        merchant_id: Optional[int] = None
    ) -> BatchArchiveInboundShipmentsResponse:
        """Archive multiple inbound shipments in batch.

        Args:
            shipment_ids: List of shipment IDs to archive
            merchant_id: Optional merchant ID to use for this request

        Returns:
            BatchArchiveInboundShipmentsResponse containing the archiving confirmation

        Raises:
            PrepBusinessError: If the API request fails
        """
        data = {
            "shipment_ids": shipment_ids
        }

        response = self._request(
            "POST",
            "/shipments/inbound/batch/archive",
            json=data,
            merchant_id=merchant_id
        )
        
        return BatchArchiveInboundShipmentsResponse.model_validate(response)

    def remove_item_from_shipment(
        self,
        shipment_id: int,
        item_id: int,
        merchant_id: Optional[int] = None
    ) -> RemoveItemFromShipmentResponse:
        """Remove an item from an inbound shipment.

        Args:
            shipment_id: The ID of the shipment
            item_id: The ID of the item to remove
            merchant_id: Optional merchant ID to use for this request

        Returns:
            RemoveItemFromShipmentResponse containing the removal confirmation

        Raises:
            PrepBusinessError: If the API request fails
        """
        data = {
            "item_id": item_id
        }

        response = self._request(
            "POST",
            f"/shipments/inbound/{shipment_id}/remove-item",
            json=data,
            merchant_id=merchant_id
        )
        
        return RemoveItemFromShipmentResponse.model_validate(response)

    def add_item_to_shipment(
        self,
        shipment_id: int,
        item_id: int,
        quantity: int,
        merchant_id: Optional[int] = None
    ) -> AddItemToShipmentResponse:
        """Add an item to an inbound shipment.

        Args:
            shipment_id: The ID of the shipment
            item_id: The ID of the item to add
            quantity: The quantity of the item to add
            merchant_id: Optional merchant ID to use for this request

        Returns:
            AddItemToShipmentResponse containing the addition confirmation

        Raises:
            PrepBusinessError: If the API request fails
        """
        data = {
            "item_id": item_id,
            "quantity": quantity
        }

        response = self._request(
            "POST",
            f"/shipments/inbound/{shipment_id}/add-item",
            json=data,
            merchant_id=merchant_id
        )
        
        return AddItemToShipmentResponse.model_validate(response)

    def get_inbound_shipment_items(
        self,
        shipment_id: int,
        merchant_id: Optional[int] = None
    ) -> ShipmentItemsResponse:
        """Get a list of items in an inbound shipment.

        Args:
            shipment_id: The ID of the shipment
            merchant_id: Optional merchant ID to use for this request

        Returns:
            ShipmentItemsResponse containing the list of items in the shipment

        Raises:
            PrepBusinessError: If the API request fails
        """
        response = self._request(
            "GET",
            f"/shipments/inbound/{shipment_id}/items",
            merchant_id=merchant_id
        )
        
        return ShipmentItemsResponse.model_validate(response)

    def update_shipment_item(
        self,
        shipment_id: int,
        item_id: int,
        expected: ExpectedItemUpdate,
        actual: ActualItemUpdate,
        merchant_id: Optional[int] = None
    ) -> UpdateShipmentItemResponse:
        """Update an item in an inbound shipment.

        Args:
            shipment_id: The ID of the shipment
            item_id: The ID of the item to update
            expected: The expected item details
            actual: The actual item details
            merchant_id: Optional merchant ID to use for this request

        Returns:
            UpdateShipmentItemResponse containing the update confirmation

        Raises:
            PrepBusinessError: If the API request fails
        """
        data = {
            "item_id": item_id,
            "expected": expected.model_dump(),
            "actual": actual.model_dump()
        }

        response = self._request(
            "POST",
            f"/shipments/inbound/{shipment_id}/update-item",
            json=data,
            merchant_id=merchant_id
        )
        
        return UpdateShipmentItemResponse.model_validate(response)

    def get_outbound_shipments(
        self,
        page: int = 1,
        per_page: int = 20,
        merchant_id: Optional[int] = None
    ) -> OutboundShipmentsResponse:
        """Get a list of all outbound shipments with pagination.

        Args:
            page: Page number to retrieve (default: 1)
            per_page: Number of items per page (default: 20)
            merchant_id: Optional merchant ID to use for this request

        Returns:
            OutboundShipmentsResponse containing the list of shipments and pagination info

        Raises:
            PrepBusinessError: If the API request fails
        """
        params = {
            "page": page,
            "per_page": per_page
        }
        
        response = self._request(
            "GET",
            "/shipments/outbound",
            params=params,
            merchant_id=merchant_id
        )
        
        return OutboundShipmentsResponse.model_validate(response)

    def get_archived_outbound_shipments(
        self,
        page: int = 1,
        per_page: int = 20,
        merchant_id: Optional[int] = None,
        search_query: Optional[str] = None
    ) -> OutboundShipmentsResponse:
        """Get a list of all archived outbound shipments with pagination and search query support.

        Args:
            page: Page number to retrieve (default: 1)
            per_page: Number of items per page (default: 20)
            merchant_id: Optional merchant ID to use for this request
            search_query: Optional search query string (q=...)

        Returns:
            OutboundShipmentsResponse containing the list of archived shipments and pagination info

        Raises:
            PrepBusinessError: If the API request fails
        """
        params = {
            "page": page,
            "per_page": per_page
        }
        if search_query:
            params["q"] = search_query
        response = self._request(
            "GET",
            "/shipments/outbound/archived",
            params=params,
            merchant_id=merchant_id
        )
        return OutboundShipmentsResponse.model_validate(response)

    def get_outbound_shipment(
        self,
        shipment_id: int,
        merchant_id: Optional[int] = None
    ) -> OutboundShipmentResponse:
        """Get detailed information about a specific outbound shipment.

        Args:
            shipment_id: The ID of the shipment to retrieve
            merchant_id: Optional merchant ID to use for this request

        Returns:
            OutboundShipmentResponse containing the detailed shipment information

        Raises:
            PrepBusinessError: If the API request fails
        """
        response = self._request(
            "GET",
            f"/shipments/outbound/{shipment_id}",
            merchant_id=merchant_id
        )
        
        return OutboundShipmentResponse.model_validate(response)

    def create_outbound_shipment(
        self,
        name: str,
        warehouse_id: int,
        notes: Optional[str] = None,
        merchant_id: Optional[int] = None
    ) -> CreateOutboundShipmentResponse:
        """Create a new outbound shipment.

        Args:
            name: The name of the shipment
            warehouse_id: The ID of the warehouse that you are sending the shipment from
            notes: Optional notes about the shipment
            merchant_id: Optional merchant ID to use for this request

        Returns:
            CreateOutboundShipmentResponse containing the created shipment ID

        Raises:
            PrepBusinessError: If the API request fails
        """
        data = {
            "name": name,
            "warehouse_id": warehouse_id
        }
        
        if notes is not None:
            data["notes"] = notes
            
        response = self._request(
            "POST",
            "/shipments/outbound",
            json=data,
            merchant_id=merchant_id
        )
        
        return CreateOutboundShipmentResponse.model_validate(response)

    def add_outbound_shipment_attachment(
        self,
        shipment_id: int,
        file_path: str,
        file_name: Optional[str] = None,
        merchant_id: Optional[int] = None
    ) -> AddOutboundShipmentAttachmentResponse:
        """Add an attachment to an outbound shipment.

        Args:
            shipment_id: The ID of the shipment to add the attachment to
            file_path: Path to the file to attach
            file_name: Optional name for the file. If not provided, the original filename will be used
            merchant_id: Optional merchant ID to use for this request

        Returns:
            AddOutboundShipmentAttachmentResponse containing the attachment details

        Raises:
            PrepBusinessError: If the API request fails
            FileNotFoundError: If the file does not exist
        """
        import os
        from pathlib import Path
        import mimetypes
        import requests
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
            
        if file_name is None:
            file_name = os.path.basename(file_path)
            
        # Determina il tipo MIME del file
        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type is None:
            mime_type = 'application/octet-stream'
            
        print(f"Preparazione upload file: {file_name} ({mime_type})")
            
        with open(file_path, 'rb') as f:
            # Crea il payload multipart/form-data passando direttamente l'oggetto file
            files = {
                'file': (file_name, f, mime_type)
            }
            
            # Imposta gli headers
            headers = {
                'Accept': 'application/json',
                'Authorization': f'Bearer {self.config.api_key}'
            }
            
            # Aggiungi merchant ID se specificato
            if merchant_id is not None:
                headers['X-Selected-Client-Id'] = str(merchant_id)
            elif self.config.default_merchant_id is not None:
                headers['X-Selected-Client-Id'] = str(self.config.default_merchant_id)
            
            print(f"Invio richiesta a /shipments/outbound/{shipment_id}/attachment")
            print(f"Headers: {headers}")
            print(f"Files: {files}")
            
            # Costruisci l'URL
            url = f"https://{self.config.company_domain}/api/shipments/outbound/{shipment_id}/attachment"
            
            # Fai la richiesta direttamente con requests
            response = requests.post(
                url,
                files=files,
                headers=headers,
                timeout=self.config.timeout
            )
            
            # Gestisci la risposta
            if response.status_code >= 400:
                error_msg = "API request failed"
                try:
                    error_data = response.json()
                    if isinstance(error_data, dict):
                        error_msg = error_data.get('message', error_msg)
                        if 'errors' in error_data:
                            error_msg += f"\nDetails: {error_data['errors']}"
                except ValueError:
                    error_msg = response.text or error_msg
                
                raise PrepBusinessError(f"{error_msg} (Status: {response.status_code})")
            
            return AddOutboundShipmentAttachmentResponse.model_validate(response.json())

    def get_outbound_shipment_items(
        self,
        shipment_id: int,
        merchant_id: Optional[int] = None
    ) -> OutboundShipmentItemsResponse:
        """Get a list of items in an outbound shipment.

        Args:
            shipment_id: The ID of the shipment
            merchant_id: Optional merchant ID to use for this request

        Returns:
            OutboundShipmentItemsResponse containing the list of items in the shipment

        Raises:
            PrepBusinessError: If the API request fails
        """
        response = self._request(
            "GET",
            f"/shipments/outbound/{shipment_id}/outbound-shipment-item",
            merchant_id=merchant_id
        )
        
        return OutboundShipmentItemsResponse.model_validate(response)

    def add_outbound_shipment_item(
        self,
        shipment_id: int,
        item_id: int,
        quantity: int,
        expiry_date: Optional[str] = None,
        merchant_id: Optional[int] = None
    ) -> AddOutboundShipmentItemResponse:
        """Add an item to an outbound shipment.

        Args:
            shipment_id: The ID of the shipment to add the item to
            item_id: The ID of the item to add
            quantity: The quantity of the item to add
            expiry_date: Optional expiry date of the item (format: YYYY-MM-DD)
            merchant_id: Optional merchant ID to use for this request

        Returns:
            AddOutboundShipmentItemResponse containing the response message

        Raises:
            PrepBusinessError: If the API request fails
        """
        data = {
            "item_id": item_id,
            "quantity": quantity
        }
        
        if expiry_date is not None:
            data["expiry_date"] = expiry_date
            
        response = self._request(
            "POST",
            f"/shipments/outbound/{shipment_id}/outbound-shipment-item",
            json=data,
            merchant_id=merchant_id
        )
        
        return AddOutboundShipmentItemResponse.model_validate(response)

    def update_outbound_shipment_item(
        self,
        shipment_id: int,
        item_id: int,
        quantity: Optional[int] = None,
        expiry_date: Optional[date] = None,
        item_group_configurations: Optional[List[ItemGroupConfigurationUpdate]] = None
    ) -> UpdateOutboundShipmentItemResponse:
        """
        Update an item in an outbound shipment.

        Args:
            shipment_id: The ID of the outbound shipment
            item_id: The ID of the item to update
            quantity: The new quantity of the item
            expiry_date: The new expiry date of the item
            item_group_configurations: List of item group configurations to update

        Returns:
            UpdateOutboundShipmentItemResponse: The response from the API

        Raises:
            PrepBusinessError: If the API request fails
        """
        data = {}
        if quantity is not None:
            data["quantity"] = quantity
        if expiry_date is not None:
            data["expiry_date"] = expiry_date.isoformat()
        if item_group_configurations is not None:
            data["item_group_configurations"] = [
                config.model_dump() for config in item_group_configurations
            ]

        response = self._request(
            "PATCH",
            f"/shipments/outbound/{shipment_id}/outbound-shipment-item/{item_id}",
            json=data
        )
        return UpdateOutboundShipmentItemResponse(**response)

    def delete_outbound_shipment_item(
        self,
        shipment_id: int,
        item_id: int,
        merchant_id: Optional[int] = None
    ) -> Dict[str, str]:
        """Rimuove un articolo da una spedizione in uscita.

        Args:
            shipment_id: ID della spedizione
            item_id: ID dell'articolo da rimuovere
            merchant_id: ID opzionale del merchant

        Returns:
            Dict contenente il messaggio di risposta

        Raises:
            PrepBusinessError: Se la richiesta API fallisce
        """
        response = self._request(
            "DELETE",
            f"/shipments/outbound/{shipment_id}/outbound-shipment-item/{item_id}",
            merchant_id=merchant_id
        )
        return response

    def get_orders(
        self,
        page: int = 1,
        per_page: int = 20,
        status: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        merchant_id: Optional[str] = None
    ) -> OrdersResponse:
        """
        Get a list of orders with optional filtering.
        
        Args:
            page (int): Page number for pagination (default: 1)
            per_page (int): Number of items per page (default: 20)
            status (str, optional): Filter by order status
            from_date (str, optional): Filter orders created after this date (YYYY-MM-DD)
            to_date (str, optional): Filter orders created before this date (YYYY-MM-DD)
            merchant_id (str, optional): Filter by merchant ID
            
        Returns:
            OrdersResponse: Response containing the list of orders
            
        Raises:
            PrepBusinessError: If the API request fails
        """
        endpoint = "/orders"
        params = {
            "page": page,
            "per_page": per_page
        }
        
        if status:
            params["status"] = status
        if from_date:
            params["from_date"] = from_date
        if to_date:
            params["to_date"] = to_date
        if merchant_id:
            params["merchant_id"] = merchant_id
            
        response = self._request(
            "GET",
            endpoint,
            params=params
        )
        return OrdersResponse(**response)

    def get_order(self, order_id: int) -> OrderResponse:
        """Get details for a specific order.
        
        Args:
            order_id: ID of the order to retrieve
            
        Returns:
            OrderResponse containing the order details
            
        Raises:
            PrepBusinessError: If the API request fails
        """
        response = self.get(f"orders/{order_id}")
        return OrderResponse.parse_obj(response)

    def upload_orders(
        self,
        channel_id: int,
        orders: List[OrderUpload],
        merchant_id: Optional[int] = None
    ) -> UploadOrdersResponse:
        """Upload multiple orders in bulk.
        
        Args:
            channel_id: The ID of the sales channel the orders were placed on
            orders: List of orders to upload
            merchant_id: Optional merchant ID to use for this request
            
        Returns:
            UploadOrdersResponse containing the upload confirmation
            
        Raises:
            PrepBusinessError: If the API request fails
            ValueError: If neither name nor first_name/last_name is provided for any order
        """
        # Validate that each order has either name or first_name/last_name
        for order in orders:
            if not order.name and not (order.first_name and order.last_name):
                raise ValueError("Each order must have either name or both first_name and last_name")
            if not order.country and not order.country_code:
                raise ValueError("Each order must have either country or country_code")

        # Convert orders to dictionaries and handle date serialization
        orders_data = []
        for order in orders:
            order_dict = order.model_dump()
            # Convert any datetime fields to ISO format strings
            for key, value in order_dict.items():
                if isinstance(value, (datetime, date)):
                    order_dict[key] = value.isoformat()
            orders_data.append(order_dict)

        data = {
            "channel_id": channel_id,
            "orders": orders_data
        }

        response = self._request(
            "POST",
            "/orders/upload",
            json=data,
            merchant_id=merchant_id
        )
        
        return UploadOrdersResponse.model_validate(response)

    def upload_shipping_label(
        self,
        order_id: int,
        file_path: str,
        merchant_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Upload a shipping label for an order.
        
        Args:
            order_id: The ID of the order to upload the shipping label for
            file_path: Path to the shipping label file (PDF, PNG, or JPG)
            merchant_id: Optional merchant ID to use for this request
            
        Returns:
            Dict containing the API response
            
        Raises:
            PrepBusinessError: If the API request fails
            FileNotFoundError: If the file does not exist
        """
        import os
        from pathlib import Path
        import mimetypes
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
            
        # Determina il tipo MIME del file
        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type is None:
            mime_type = 'application/octet-stream'
            
        # Estrai il nome del file
        file_name = os.path.basename(file_path)
            
        with open(file_path, 'rb') as f:
            # Crea il payload multipart/form-data passando direttamente l'oggetto file
            files = {
                'file': (file_name, f, mime_type)
            }
            
            response = self._request(
                "POST",
                f"/orders/{order_id}/uploadShippingLabel",
                files=files,
                merchant_id=merchant_id
            )
            
            return response 

    def mark_order_as_shipped(
        self,
        order_id: int,
        carrier: str,
        tracking_number: str,
        merchant_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Mark an order as shipped and add a tracking number.
        Args:
            order_id: The ID of the order to mark as shipped
            carrier: The carrier used for shipping (fedex, ups, usps, etc.)
            tracking_number: The tracking number for the shipment
            merchant_id: Optional merchant ID to use for this request
        Returns:
            Dict containing the API response
        Raises:
            PrepBusinessError: If the API request fails
        """
        data = {
            "carrier": carrier,
            "tracking_number": tracking_number
        }
        response = self._request(
            "POST",
            f"/orders/{order_id}/markAsShipped",
            json=data,
            merchant_id=merchant_id
        )
        return response 

    def get_services(
        self,
        merchant_id: Optional[int] = None
    ) -> ServicesResponse:
        """Get a list of services offered at the warehouse.

        Args:
            merchant_id: Optional merchant ID to use for this request

        Returns:
            ServicesResponse containing the list of services

        Raises:
            PrepBusinessError: If the API request fails
        """
        response = self._request(
            "GET",
            "/services",
            merchant_id=merchant_id
        )
        
        return ServicesResponse.model_validate(response)
        
    def get_warehouses(
        self,
        merchant_id: Optional[int] = None
    ) -> WarehousesResponse:
        """Get a list of warehouses associated with the merchant.

        Args:
            merchant_id: Optional merchant ID to use for this request

        Returns:
            WarehousesResponse containing the list of warehouses

        Raises:
            PrepBusinessError: If the API request fails
        """
        response = self._request(
            "GET",
            "/warehouses",
            merchant_id=merchant_id
        )
        
        return WarehousesResponse.model_validate(response)

    def create_adjustment(
        self,
        item_id: int,
        warehouse_id: int,
        quantity: int,
        reason: AdjustmentReason,
        notes: Optional[str] = None,
        merchant_id: Optional[int] = None
    ) -> CreateAdjustmentResponse:
        """Create a new inventory adjustment.

        Args:
            item_id: ID of the item you are creating an adjustment for
            warehouse_id: ID of the warehouse you are creating the adjustment in
            quantity: The amount you are adjusting by (can be negative or positive)
            reason: Reason for the adjustment (lost, found, damaged, other)
            notes: Optional notes to explain the reason for the adjustment
            merchant_id: Optional merchant ID to use for this request

        Returns:
            CreateAdjustmentResponse containing the created adjustment details

        Raises:
            PrepBusinessError: If the API request fails
        """
        data = {
            "item_id": item_id,
            "warehouse_id": warehouse_id,
            "quantity": quantity,
            "reason": reason.value
        }
        
        if notes is not None:
            data["notes"] = notes
            
        response = self._request(
            "POST",
            "/adjustments",
            json=data,
            merchant_id=merchant_id
        )
        
        return CreateAdjustmentResponse.model_validate(response)
        
    def get_merchants(self) -> MerchantsResponse:
        """Get a list of all merchants.

        Returns:
            MerchantsResponse containing the merchant data

        Raises:
            PrepBusinessError: If the API request fails
        """
        response = self._request(
            "GET",
            "/merchants"
        )
        
        return MerchantsResponse.model_validate(response)
        
    def get_webhooks(self) -> WebhooksResponse:
        """Get a list of service provider webhooks.
        
        This endpoint returns webhooks configured for the service provider (PrepBusiness).

        Returns:
            WebhooksResponse containing the list of webhooks

        Raises:
            PrepBusinessError: If the API request fails
        """
        response = self._request(
            "GET",
            "/webhooks"
        )
        
        return WebhooksResponse.model_validate(response)
        
    def get_merchant_webhooks(self, merchant_id: Optional[int] = None) -> WebhooksResponse:
        """Get a list of webhooks for a specific merchant.
        
        Args:
            merchant_id: ID of the merchant to get webhooks for. If not provided,
                         the default merchant ID will be used.

        Returns:
            WebhooksResponse containing the list of webhooks

        Raises:
            PrepBusinessError: If the API request fails
        """
        merchant_id = merchant_id or self.config.default_merchant_id
        
        if merchant_id is None:
            raise ValueError("No merchant ID provided and no default merchant ID set")
            
        response = self._request(
            "GET",
            f"/merchants/{merchant_id}/webhooks"
        )
        
        return WebhooksResponse.model_validate(response)
        
    def create_webhook(
        self,
        url: str,
        invoice_created: bool = False,
        inbound_shipment_notes_updated: bool = False,
        inbound_shipment_created: bool = False,
        inbound_shipment_shipped: bool = False,
        inbound_shipment_received: bool = False,
        outbound_shipment_notes_updated: bool = False,
        outbound_shipment_created: bool = False,
        outbound_shipment_shipped: bool = False,
        outbound_shipment_closed: bool = False,
        order_shipped: bool = False
    ) -> WebhookResponse:
        """Create a new service provider webhook.
        
        Args:
            url: The URL where webhook events will be sent
            invoice_created: Whether to notify when invoices are created
            inbound_shipment_notes_updated: Whether to notify when inbound shipment notes are updated
            inbound_shipment_created: Whether to notify when inbound shipments are created
            inbound_shipment_shipped: Whether to notify when inbound shipments are shipped
            inbound_shipment_received: Whether to notify when inbound shipments are received
            outbound_shipment_notes_updated: Whether to notify when outbound shipment notes are updated
            outbound_shipment_created: Whether to notify when outbound shipments are created
            outbound_shipment_shipped: Whether to notify when outbound shipments are shipped
            outbound_shipment_closed: Whether to notify when outbound shipments are closed
            order_shipped: Whether to notify when orders are shipped
            
        Returns:
            WebhookResponse containing the created webhook details
            
        Raises:
            PrepBusinessError: If the API request fails
        """
        webhook_data = {
            "url": url,
            "types": {
                "invoice": {
                    "created": invoice_created
                },
                "inbound_shipment": {
                    "notes_updated": inbound_shipment_notes_updated,
                    "created": inbound_shipment_created,
                    "shipped": inbound_shipment_shipped,
                    "received": inbound_shipment_received
                },
                "outbound_shipment": {
                    "notes_updated": outbound_shipment_notes_updated,
                    "created": outbound_shipment_created,
                    "shipped": outbound_shipment_shipped,
                    "closed": outbound_shipment_closed
                },
                "order": {
                    "shipped": order_shipped
                }
            }
        }
        
        response = self._request(
            "POST",
            "/webhooks",
            json=webhook_data
        )
        
        return WebhookResponse.model_validate(response)
        
    def create_merchant_webhook(
        self,
        merchant_id: int,
        url: str,
        invoice_created: bool = False,
        inbound_shipment_notes_updated: bool = False,
        inbound_shipment_created: bool = False,
        inbound_shipment_shipped: bool = False,
        inbound_shipment_received: bool = False,
        outbound_shipment_notes_updated: bool = False,
        outbound_shipment_created: bool = False,
        outbound_shipment_shipped: bool = False,
        outbound_shipment_closed: bool = False,
        order_shipped: bool = False
    ) -> WebhookResponse:
        """Create a new merchant webhook.
        
        Args:
            merchant_id: ID of the merchant to create the webhook for
            url: The URL where webhook events will be sent
            invoice_created: Whether to notify when invoices are created
            inbound_shipment_notes_updated: Whether to notify when inbound shipment notes are updated
            inbound_shipment_created: Whether to notify when inbound shipments are created
            inbound_shipment_shipped: Whether to notify when inbound shipments are shipped
            inbound_shipment_received: Whether to notify when inbound shipments are received
            outbound_shipment_notes_updated: Whether to notify when outbound shipment notes are updated
            outbound_shipment_created: Whether to notify when outbound shipments are created
            outbound_shipment_shipped: Whether to notify when outbound shipments are shipped
            outbound_shipment_closed: Whether to notify when outbound shipments are closed
            order_shipped: Whether to notify when orders are shipped
            
        Returns:
            WebhookResponse containing the created webhook details
            
        Raises:
            PrepBusinessError: If the API request fails
        """
        webhook_data = {
            "url": url,
            "types": {
                "invoice": {
                    "created": invoice_created
                },
                "inbound_shipment": {
                    "notes_updated": inbound_shipment_notes_updated,
                    "created": inbound_shipment_created,
                    "shipped": inbound_shipment_shipped,
                    "received": inbound_shipment_received
                },
                "outbound_shipment": {
                    "notes_updated": outbound_shipment_notes_updated,
                    "created": outbound_shipment_created,
                    "shipped": outbound_shipment_shipped,
                    "closed": outbound_shipment_closed
                },
                "order": {
                    "shipped": order_shipped
                }
            }
        }
        
        response = self._request(
            "POST",
            f"/merchants/{merchant_id}/webhooks",
            json=webhook_data
        )
        
        return WebhookResponse.model_validate(response)
        
    def update_webhook(
        self,
        webhook_id: int,
        url: str,
        invoice_created: bool = False,
        inbound_shipment_notes_updated: bool = False,
        inbound_shipment_created: bool = False,
        inbound_shipment_shipped: bool = False,
        inbound_shipment_received: bool = False,
        outbound_shipment_notes_updated: bool = False,
        outbound_shipment_created: bool = False,
        outbound_shipment_shipped: bool = False,
        outbound_shipment_closed: bool = False,
        order_shipped: bool = False
    ) -> WebhookResponse:
        """Update an existing service provider webhook.
        
        Args:
            webhook_id: ID of the webhook to update
            url: The URL where webhook events will be sent
            invoice_created: Whether to notify when invoices are created
            inbound_shipment_notes_updated: Whether to notify when inbound shipment notes are updated
            inbound_shipment_created: Whether to notify when inbound shipments are created
            inbound_shipment_shipped: Whether to notify when inbound shipments are shipped
            inbound_shipment_received: Whether to notify when inbound shipments are received
            outbound_shipment_notes_updated: Whether to notify when outbound shipment notes are updated
            outbound_shipment_created: Whether to notify when outbound shipments are created
            outbound_shipment_shipped: Whether to notify when outbound shipments are shipped
            outbound_shipment_closed: Whether to notify when outbound shipments are closed
            order_shipped: Whether to notify when orders are shipped
            
        Returns:
            WebhookResponse containing the updated webhook details
            
        Raises:
            PrepBusinessError: If the API request fails
        """
        webhook_data = {
            "url": url,
            "types": {
                "invoice": {
                    "created": invoice_created
                },
                "inbound_shipment": {
                    "notes_updated": inbound_shipment_notes_updated,
                    "created": inbound_shipment_created,
                    "shipped": inbound_shipment_shipped,
                    "received": inbound_shipment_received
                },
                "outbound_shipment": {
                    "notes_updated": outbound_shipment_notes_updated,
                    "created": outbound_shipment_created,
                    "shipped": outbound_shipment_shipped,
                    "closed": outbound_shipment_closed
                },
                "order": {
                    "shipped": order_shipped
                }
            }
        }
        
        response = self._request(
            "PUT",
            f"/webhooks/{webhook_id}",
            json=webhook_data
        )
        
        return WebhookResponse.model_validate(response)
        
    def update_merchant_webhook(
        self,
        merchant_id: int,
        webhook_id: int,
        url: str,
        invoice_created: bool = False,
        inbound_shipment_notes_updated: bool = False,
        inbound_shipment_created: bool = False,
        inbound_shipment_shipped: bool = False,
        inbound_shipment_received: bool = False,
        outbound_shipment_notes_updated: bool = False,
        outbound_shipment_created: bool = False,
        outbound_shipment_shipped: bool = False,
        outbound_shipment_closed: bool = False,
        order_shipped: bool = False
    ) -> WebhookResponse:
        """Update an existing merchant webhook.
        
        Args:
            merchant_id: ID of the merchant the webhook belongs to
            webhook_id: ID of the webhook to update
            url: The URL where webhook events will be sent
            invoice_created: Whether to notify when invoices are created
            inbound_shipment_notes_updated: Whether to notify when inbound shipment notes are updated
            inbound_shipment_created: Whether to notify when inbound shipments are created
            inbound_shipment_shipped: Whether to notify when inbound shipments are shipped
            inbound_shipment_received: Whether to notify when inbound shipments are received
            outbound_shipment_notes_updated: Whether to notify when outbound shipment notes are updated
            outbound_shipment_created: Whether to notify when outbound shipments are created
            outbound_shipment_shipped: Whether to notify when outbound shipments are shipped
            outbound_shipment_closed: Whether to notify when outbound shipments are closed
            order_shipped: Whether to notify when orders are shipped
            
        Returns:
            WebhookResponse containing the updated webhook details
            
        Raises:
            PrepBusinessError: If the API request fails
        """
        webhook_data = {
            "url": url,
            "types": {
                "invoice": {
                    "created": invoice_created
                },
                "inbound_shipment": {
                    "notes_updated": inbound_shipment_notes_updated,
                    "created": inbound_shipment_created,
                    "shipped": inbound_shipment_shipped,
                    "received": inbound_shipment_received
                },
                "outbound_shipment": {
                    "notes_updated": outbound_shipment_notes_updated,
                    "created": outbound_shipment_created,
                    "shipped": outbound_shipment_shipped,
                    "closed": outbound_shipment_closed
                },
                "order": {
                    "shipped": order_shipped
                }
            }
        }
        
        response = self._request(
            "PUT",
            f"/merchants/{merchant_id}/webhooks/{webhook_id}",
            json=webhook_data
        )
        
        return WebhookResponse.model_validate(response)
        
    def delete_webhook(self, webhook_id: int) -> DeleteWebhookResponse:
        """Delete a service provider webhook.
        
        Args:
            webhook_id: ID of the webhook to delete
            
        Returns:
            DeleteWebhookResponse with a success message
            
        Raises:
            PrepBusinessError: If the API request fails
        """
        response = self._request(
            "DELETE",
            f"/webhooks/{webhook_id}"
        )
        
        return DeleteWebhookResponse.model_validate(response)
        
    def delete_merchant_webhook(self, merchant_id: int, webhook_id: int) -> DeleteWebhookResponse:
        """Delete a merchant webhook.
        
        Args:
            merchant_id: ID of the merchant the webhook belongs to
            webhook_id: ID of the webhook to delete
            
        Returns:
            DeleteWebhookResponse with a success message
            
        Raises:
            PrepBusinessError: If the API request fails
        """
        response = self._request(
            "DELETE",
            f"/merchants/{merchant_id}/webhooks/{webhook_id}"
        )
        
        return DeleteWebhookResponse.model_validate(response)

    def get_shipment_items(
        self,
        shipment_id: int,
        merchant_id: Optional[int] = None
    ) -> ShipmentItemsResponse:
        """Alias for get_inbound_shipment_items for backward compatibility.
        This method is deprecated and will be removed in a future version.
        Please use get_inbound_shipment_items instead.
        """
        return self.get_inbound_shipment_items(shipment_id, merchant_id) 