from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union, TypeVar, Generic
from datetime import datetime, date
from dataclasses import dataclass

class PrepBusinessError(Exception):
    """Base exception for PrepBusiness API errors."""
    pass

class AuthenticationError(PrepBusinessError):
    """Raised when authentication fails."""
    pass

T = TypeVar('T')

class PaginatedResponse(BaseModel, Generic[T]):
    """Response model for paginated data."""
    data: List[T] = Field(..., description="List of items in the current page")
    current_page: int = Field(..., description="Current page number")
    from_: int = Field(..., alias="from", description="Start index of the current page")
    to: int = Field(..., description="End index of the current page")
    total: int = Field(..., description="Total number of items across all pages")
    last_page: int = Field(..., description="Last page number")
    per_page: int = Field(..., description="Number of items per page")

class ChannelType(str, Enum):
    """Supported channel types."""
    AMAZON = "amazon"
    EBAY = "ebay"
    SHOPIFY = "shopify"
    WOOCOMMERCE = "woocommerce"
    CUSTOM = "custom"
    # Add more channel types as needed

class ConnectionStatus(str, Enum):
    """Possible connection statuses for a channel."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    ERROR = "error"
    UNAUTHORIZED = "unauthorized"  # Aggiunto nuovo stato

class Channel(BaseModel):
    """Model representing a sales channel."""
    id: int = Field(..., description="Unique identifier for the channel")
    team_id: int = Field(..., description="ID of the team this channel belongs to")
    type: ChannelType = Field(..., description="Type of the channel (e.g. amazon, ebay)")
    nickname: str = Field(..., description="User-defined name for the channel")
    channel_account_id: Optional[str] = Field(None, description="ID of the channel account")
    connection_status: ConnectionStatus = Field(..., description="Current connection status")
    country_id: Optional[str] = Field(None, alias="countryId", description="Country ID for the channel")

class Identifier(BaseModel):
    """Model representing a product identifier."""
    id: int = Field(..., description="Unique identifier")
    inventory_item_id: int = Field(..., description="ID of the associated inventory item")
    identifier: str = Field(..., description="The identifier value")
    identifier_type: str = Field(..., description="Type of identifier (e.g. EAN, ASIN, FNSKU)")
    created_at: Optional[str] = Field(None, description="Creation timestamp")
    updated_at: Optional[str] = Field(None, description="Last update timestamp")

class Image(BaseModel):
    """Model representing a product image."""
    id: int = Field(..., description="Unique identifier")
    listing_id: int = Field(..., description="ID of the associated listing")
    large_url: str = Field(..., description="URL of the large image")
    thumbnail_url: str = Field(..., description="URL of the thumbnail image")

class ProductLink(BaseModel):
    """Model representing a link between a listing and a product."""
    id: int = Field(..., description="Unique identifier")
    created_at: str = Field(..., description="Creation timestamp")
    listing_id: int = Field(..., description="ID of the associated listing")
    product_id: int = Field(..., description="ID of the linked product")

class ListingStatus(str, Enum):
    """Possible statuses for a listing."""
    SYNCED = "synced"
    PENDING = "pending"
    ERROR = "error"

class Listing(BaseModel):
    """Model representing a product listing."""
    id: int = Field(..., description="Unique identifier")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")
    channel_id: int = Field(..., description="ID of the associated channel")
    sku: str = Field(..., description="Stock Keeping Unit")
    title: str = Field(..., description="Product title")
    condition: Optional[str] = Field(None, description="Product condition")
    condition_note: Optional[str] = Field(None, description="Notes about the condition")
    channel_identifier: str = Field(..., description="Identifier in the channel")
    length_mm: Optional[float] = Field(None, description="Length in millimeters")
    width_mm: Optional[float] = Field(None, description="Width in millimeters")
    height_mm: Optional[float] = Field(None, description="Height in millimeters")
    weight_gm: Optional[float] = Field(None, description="Weight in grams")
    status: ListingStatus = Field(..., description="Current status of the listing")
    flags: List[str] = Field(default_factory=list, description="List of flags")
    identifiers: List[Identifier] = Field(..., description="List of product identifiers")
    images: List[Image] = Field(..., description="List of product images")
    product_link: Optional[ProductLink] = Field(None, description="Link to the product")

class ListingResponse(BaseModel):
    """Model representing the response from the listings endpoint."""
    data: List[Listing] = Field(..., description="List of listings")
    total: int = Field(..., description="Total number of listings")
    current_page: int = Field(..., description="Current page number")
    last_page: int = Field(..., description="Last page number")
    per_page: int = Field(..., description="Number of items per page")
    from_: int = Field(..., alias="from", description="Starting index")
    to: int = Field(..., description="Ending index")

class ChargeStatus(str, Enum):
    """Possible statuses for a charge."""
    OPEN = "Open"
    CLOSED = "Closed"
    VOID = "Void"
    INVOICED = "Invoiced"

class ChargeCategory(str, Enum):
    """Possible categories for a charge."""
    ITEM_STORAGE = "ItemStorage"
    OUTBOUND_SHIPMENT = "OutboundShipment"
    INBOUND_SHIPMENT = "InboundShipment"
    ADJUSTMENT = "Adjustment"
    BUNDLE_CREATION = "BundleCreation"
    BUNDLE_BREAKUP = "BundleBreakup"
    DISPOSAL = "Disposal"
    REMOVAL = "Removal"
    RETURN = "Return"
    STORAGE = "Storage"
    SUBSCRIPTION = "Subscription"
    TRANSFER = "Transfer"
    PICK_AND_PACK = "PickAndPack"
    SHIPPING = "Shipping"
    HANDLING = "Handling"
    RECEIVING = "Receiving"
    LABELING = "Labeling"
    PACKAGING = "Packaging"
    INSPECTION = "Inspection"
    PROCESSING = "Processing"
    RESTOCKING = "Restocking"
    INVENTORY_ADJUSTMENT = "InventoryAdjustment"
    CUSTOM = "Custom"

class PaginationLink(BaseModel):
    """Model for pagination links."""
    url: Optional[str] = Field(None, description="URL for the pagination link")
    label: str = Field(..., description="Label for the pagination link")
    active: bool = Field(..., description="Whether this is the current page")

class Charge(BaseModel):
    """Model representing a billing charge."""
    id: int = Field(..., description="Unique identifier for the charge")
    created_at: str = Field(..., description="Creation timestamp")
    charger_type: str = Field(..., description="Type of entity that created the charge")
    charger_id: str = Field(..., description="ID of the entity that created the charge")
    chargee_type: str = Field(..., description="Type of entity being charged")
    chargee_id: str = Field(..., description="ID of the entity being charged")
    description: str = Field(..., description="Description of the charge")
    category: ChargeCategory = Field(..., description="Category of the charge")
    currency: str = Field(..., description="Currency code")
    amount: float = Field(..., description="Amount of the charge")
    is_void: Optional[bool] = Field(None, description="Whether the charge is void")
    is_invoiced: Optional[bool] = Field(None, description="Whether the charge has been invoiced")
    status: ChargeStatus = Field(..., description="Current status of the charge")

class ChargesResponse(BaseModel):
    """Model representing the response from the charges endpoint."""
    current_page: int = Field(..., description="Current page number")
    data: List[Charge] = Field(..., description="List of charges")
    first_page_url: str = Field(..., description="URL for the first page")
    from_: int = Field(..., alias="from", description="Starting index")
    last_page: int = Field(..., description="Last page number")
    last_page_url: str = Field(..., description="URL for the last page")
    links: List[PaginationLink] = Field(..., description="Pagination links")
    next_page_url: Optional[str] = Field(None, description="URL for the next page")
    path: str = Field(..., description="Base path for the endpoint")
    per_page: int = Field(..., description="Number of items per page")
    prev_page_url: Optional[str] = Field(None, description="URL for the previous page")
    to: int = Field(..., description="Ending index")
    total: int = Field(..., description="Total number of items")

class ChargeableItem(BaseModel):
    """Model representing a chargeable item."""
    id: Optional[int] = Field(None, description="Unique identifier")
    created_at: Optional[str] = Field(None, description="Creation timestamp")
    updated_at: Optional[str] = Field(None, description="Last update timestamp")
    name: Optional[str] = Field(None, description="Name of the item")
    type: Optional[str] = Field(None, description="Type of the item")
    unit: Optional[str] = Field(None, description="Unit of measurement")
    when_to_charge: Optional[str] = Field(None, description="When to charge for this item")
    charge: Optional[str] = Field(None, description="Charge amount")
    advanced_options: Optional[dict] = Field(None, description="Advanced options")
    service_provider_id: Optional[int] = Field(None, description="ID of the service provider")
    price_records: List[dict] = Field(default_factory=list, description="Price records")
    archived_at: Optional[str] = Field(None, description="Archival timestamp")

class ChargeItem(BaseModel):
    """Model representing a charge item."""
    id: int = Field(..., description="Unique identifier")
    charge_id: int = Field(..., description="ID of the associated charge")
    parent_id: Optional[int] = Field(None, description="ID of the parent item")
    chargeable_item: Optional[dict] = Field(None, description="Chargeable item details")
    chargeable_item_id: Optional[str] = Field(None, description="ID of the chargeable item")
    chargeable_item_type: Optional[str] = Field(None, description="Type of the chargeable item")
    description: str = Field(..., description="Description of the charge item")
    is_amendment: bool = Field(..., description="Whether this is an amendment")
    units: int = Field(..., description="Number of units")
    unit_price_amount: float = Field(..., description="Price per unit")
    line_price_amount: float = Field(..., description="Total price for the line")

class ChargeDetails(BaseModel):
    """Model representing detailed charge information."""
    id: int = Field(..., description="Unique identifier for the charge")
    charger_id: str = Field(..., description="ID of the entity that created the charge")
    charger_type: str = Field(..., description="Type of entity that created the charge")
    chargee_id: str = Field(..., description="ID of the entity being charged")
    chargee_type: str = Field(..., description="Type of entity being charged")
    created_at: str = Field(..., description="Creation timestamp")
    currency: str = Field(..., description="Currency code")
    price: float = Field(..., description="Price of the charge")
    status: ChargeStatus = Field(..., description="Current status of the charge")
    category: ChargeCategory = Field(..., description="Category of the charge")
    description: str = Field(..., description="Description of the charge")
    amount: float = Field(..., description="Amount of the charge")
    stripe_invoice_item_id: Optional[str] = Field(None, description="Stripe invoice item ID")

class ChargeDetailsResponse(BaseModel):
    """Model representing the response from the charge details endpoint."""
    charge: ChargeDetails = Field(..., description="Detailed charge information")
    charge_items: List[ChargeItem] = Field(..., description="List of charge items")

class InvoiceStatus(str, Enum):
    """Possible statuses for an invoice."""
    DRAFT = "Draft"
    OPEN = "Open"
    PAID = "Paid"
    VOID = "Void"
    FINALIZED = "Finalized"

class Invoice(BaseModel):
    """Model representing an invoice."""
    id: int = Field(..., description="Unique identifier for the invoice")
    charger_id: str = Field(..., description="ID of the entity that created the invoice")
    charger_type: str = Field(..., description="Type of entity that created the invoice")
    chargee_id: str = Field(..., description="ID of the entity being invoiced")
    chargee_type: str = Field(..., description="Type of entity being invoiced")
    created_at: str = Field(..., description="Creation timestamp")
    currency: str = Field(..., description="Currency code")
    status: InvoiceStatus = Field(..., description="Current status of the invoice")
    stripe_invoice_status: Optional[str] = Field(None, description="Status of the Stripe invoice")
    stripe_invoice_id: Optional[str] = Field(None, description="ID of the Stripe invoice")
    description: Optional[str] = Field(None, description="Description of the invoice")
    total: float = Field(..., description="Total amount of the invoice")

class InvoicesResponse(BaseModel):
    """Model representing the response from the invoices endpoint."""
    invoices: List[Invoice] = Field(..., description="List of invoices")

class CreateInvoiceResponse(BaseModel):
    """Model representing the response from creating an invoice."""
    message: str = Field(..., description="Response message")
    invoice: Invoice = Field(..., description="The created invoice")

class InventoryImage(BaseModel):
    """Model representing an inventory item image."""
    id: int = Field(..., description="Unique identifier")
    path: Optional[str] = Field(None, description="Image path")
    large_url: Optional[str] = Field(None, description="URL of the large image")
    thumbnail_url: Optional[str] = Field(None, description="URL of the thumbnail")
    imageable_id: int = Field(..., description="ID of the associated item")
    imageable_type: str = Field(..., description="Type of the imageable item")

class InventoryIdentifier(BaseModel):
    """Model representing an inventory item identifier."""
    id: int = Field(..., description="Unique identifier")
    created_at: Optional[str] = Field(None, description="Creation timestamp")
    updated_at: Optional[str] = Field(None, description="Last update timestamp")
    item_id: int = Field(..., description="ID of the associated item")
    identifier: str = Field(..., description="The identifier value")
    identifier_type: str = Field(..., description="Type of identifier (e.g. ASIN, FNSKU, EAN)")

class ItemImage(BaseModel):
    """Model for an item image."""
    id: int
    path: Optional[str] = None
    large_url: str
    thumbnail_url: str
    imageable_id: int
    imageable_type: str

class ItemIdentifier(BaseModel):
    """Model for an item identifier."""
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    item_id: int
    identifier: str
    identifier_type: str

class ItemGroupConfiguration(BaseModel):
    """Model for an item group configuration."""
    id: int
    created_at: datetime
    updated_at: datetime
    item_id: int
    quantity: int
    type: str
    weight_gm: int
    length_mm: int
    width_mm: int
    height_mm: int
    contains: Optional[Any] = None
    default: bool

class CompanyServicePivot(BaseModel):
    """Model for the pivot table between outbound shipment items and company services."""
    outbound_shipment_item_id: int
    company_service_id: int
    created_at: datetime
    updated_at: datetime

class CompanyService(BaseModel):
    """Model for a company service."""
    id: int
    created_at: datetime
    updated_at: datetime
    name: str
    type: str
    unit: str
    when_to_charge: str
    charge: str
    advanced_options: List[Any]
    service_provider_id: int
    price_records: List[Any]
    archived_at: Optional[datetime] = None
    pivot: CompanyServicePivot

class InventoryItem(BaseModel):
    """Model for an inventory item."""
    id: int
    created_at: datetime
    updated_at: datetime
    team_id: int
    merchant_sku: str
    title: str
    condition: Optional[str] = None
    condition_note: Optional[str] = None
    bundle_id: Optional[int] = None
    length_mm: Optional[int] = None
    width_mm: Optional[int] = None
    height_mm: Optional[int] = None
    weight_gm: Optional[int] = None
    quantity_in_stock: Optional[int] = 0
    available_quantity: Optional[int] = 0
    allocated_quantity: Optional[int] = 0
    unavailable_quantity: Optional[int] = 0
    inbound_quantity: Optional[int] = 0
    fnsku: Optional[str] = ""
    asin: Optional[str] = ""
    searchableIdentifiers: Optional[str] = ""
    prep_instructions: List[Any] = Field(default_factory=list)
    images: List[ItemImage] = Field(default_factory=list)
    identifiers: List[ItemIdentifier] = Field(default_factory=list)
    bundle: Optional[Any] = None
    listings: List[Any] = Field(default_factory=list)
    item_group_configurations: List[ItemGroupConfiguration] = Field(default_factory=list)
    tags: List[Any] = Field(default_factory=list)

class OutboundShipmentItem(BaseModel):
    """Model for an outbound shipment item."""
    id: int
    created_at: datetime
    updated_at: datetime
    shipment_id: int
    item_id: int
    quantity: int
    case_quantity: Optional[int] = None
    expiry_date: Optional[datetime] = None
    cost_per_item: Optional[float] = None
    item: InventoryItem
    bundle: Optional[Any] = None
    item_group_configurations: List[Any] = Field(default_factory=list)
    moves: List[Any] = Field(default_factory=list)
    company_services: List[CompanyService] = Field(default_factory=list)

class OutboundShipmentItemsResponse(BaseModel):
    """Response model for outbound shipment items."""
    items: List[OutboundShipmentItem]

class InventoryItemResponse(BaseModel):
    """Model representing the response from the inventory item endpoint."""
    data: Optional[InventoryItem] = Field(None, description="The inventory item details")
    message: Optional[str] = Field(None, description="Response message")
    item_details: Optional[InventoryItem] = Field(None, description="The inventory item details (alternative field name)")
    item: Optional[InventoryItem] = Field(None, description="The inventory item details (alternative field name)")

    @property
    def get_item(self) -> InventoryItem:
        """Get the inventory item from either data, item_details, or item field."""
        if self.data is not None:
            return self.data
        if self.item_details is not None:
            return self.item_details
        if self.item is not None:
            return self.item
        raise ValueError("No inventory item data found in response")

class InventoryResponse(BaseModel):
    """Model representing the response from the inventory endpoint."""
    current_page: int = Field(..., description="Current page number")
    data: List[InventoryItem] = Field(..., description="List of inventory items")
    first_page_url: str = Field(..., description="URL for the first page")
    from_: Optional[int] = Field(None, alias="from", description="Starting index")
    last_page: int = Field(..., description="Last page number")
    last_page_url: str = Field(..., description="URL for the last page")
    links: List[PaginationLink] = Field(..., description="Pagination links")
    next_page_url: Optional[str] = Field(None, description="URL for the next page")
    path: str = Field(..., description="Base path for the endpoint")
    per_page: int = Field(..., description="Number of items per page")
    prev_page_url: Optional[str] = Field(None, description="URL for the previous page")
    to: Optional[int] = Field(None, description="Ending index")
    total: int = Field(..., description="Total number of items")

class InventorySearchResponse(BaseModel):
    """Model representing the response from the inventory search endpoint."""
    items: List[InventoryItem] = Field(..., description="List of matching inventory items")

class InboundShipmentStatus(str, Enum):
    """Possible statuses for an inbound shipment."""
    DRAFT = "draft"
    SHIPPED = "shipped"
    RECEIVED = "received"
    ARCHIVED = "archived"
    OPEN = "open"  # Added new status

class InboundShipment(BaseModel):
    """Model representing an inbound shipment."""
    id: int = Field(..., description="Unique identifier for the shipment")
    created_at: datetime = Field(..., description="When the shipment was created")
    updated_at: datetime = Field(..., description="When the shipment was last updated")
    team_id: int = Field(..., description="ID of the team that owns the shipment")
    name: str = Field(..., description="Name of the shipment")
    notes: Optional[str] = Field(None, description="Notes about the shipment")
    warehouse_id: int = Field(..., description="ID of the warehouse")
    received_at: Optional[datetime] = Field(None, description="When the shipment was received")
    internal_notes: Optional[str] = Field(None, description="Internal notes about the shipment")
    archived_at: Optional[datetime] = Field(None, description="When the shipment was archived")
    shipped_at: Optional[datetime] = Field(None, description="When the shipment was shipped")
    checked_in_at: Optional[datetime] = Field(None, description="When the shipment was checked in")
    deleted_at: Optional[datetime] = Field(None, description="When the shipment was deleted")
    currency: str = Field(..., description="Currency code")
    eta: Optional[datetime] = Field(None, description="Estimated time of arrival")
    reference_id: str = Field(..., description="Reference ID for the shipment")
    migrated: bool = Field(..., description="Whether the shipment was migrated")
    status: InboundShipmentStatus = Field(..., description="Current status of the shipment")

class InboundShipmentsResponse(BaseModel):
    """Response model for inbound shipments with pagination."""
    current_page: int = Field(..., description="Current page number")
    data: List[InboundShipment] = Field(..., description="List of inbound shipments")
    first_page_url: str = Field(..., description="URL for the first page")
    from_: int = Field(..., alias="from", description="Starting index of the current page")
    last_page: int = Field(..., description="Last page number")
    last_page_url: str = Field(..., description="URL for the last page")
    links: List[PaginationLink] = Field(..., description="List of pagination links")
    next_page_url: Optional[str] = Field(None, description="URL for the next page")
    path: str = Field(..., description="Base path for the API endpoint")
    per_page: int = Field(..., description="Number of items per page")
    prev_page_url: Optional[str] = Field(None, description="URL for the previous page")
    to: int = Field(..., description="Ending index of the current page")
    total: int = Field(..., description="Total number of items")

class TrackingNumber(BaseModel):
    """Model representing a tracking number for a shipment."""
    id: int = Field(..., description="Unique identifier for the tracking number")
    status: str = Field(..., description="Current status of the tracking")
    number: str = Field(..., description="Tracking number")
    carrier: str = Field(..., description="Carrier name")
    service_level: Optional[str] = Field(None, description="Service level of the shipment")
    eta: Optional[datetime] = Field(None, description="Estimated time of arrival")
    transit_at: Optional[datetime] = Field(None, description="When the shipment went into transit")
    delivered_at: Optional[datetime] = Field(None, description="When the shipment was delivered")
    returned_at: Optional[datetime] = Field(None, description="When the shipment was returned")
    failed_at: Optional[datetime] = Field(None, description="When the shipment failed")
    package_identifier: Optional[str] = Field(None, description="Package identifier")
    tracking_url: Optional[str] = Field(None, description="URL to track the shipment")

class Address(BaseModel):
    """Model representing an address."""
    id: int = Field(..., description="Unique identifier for the address")
    created_at: Optional[datetime] = Field(None, description="When the address was created")
    updated_at: Optional[datetime] = Field(None, description="When the address was last updated")
    addressable_type: Optional[str] = Field(None, description="Type of entity this address belongs to")
    addressable_id: Optional[int] = Field(None, description="ID of the entity this address belongs to")
    address_line_1: str = Field(..., description="First line of the address")
    address_line_2: Optional[str] = Field(None, description="Second line of the address")
    address_line_3: Optional[str] = Field(None, description="Third line of the address")
    city: str = Field(..., description="City")
    state_province: str = Field(..., description="State or province")
    country_code: str = Field(..., description="Country code")
    postal_code: str = Field(..., description="Postal code")
    phone_number: Optional[str] = Field(None, description="Phone number")
    is_residential: bool = Field(..., description="Whether this is a residential address")

class Warehouse(BaseModel):
    """Model representing a warehouse."""
    id: int = Field(..., description="Unique identifier for the warehouse")
    name: str = Field(..., description="Name of the warehouse")
    service_provider_id: Optional[int] = Field(None, description="ID of the service provider")
    default_address_id: Optional[int] = Field(None, description="ID of the default address")
    deletable: Optional[bool] = Field(None, description="Whether the warehouse can be deleted")
    default_address: Address = Field(..., description="Default address of the warehouse")
    addresses: List[Address] = Field(default_factory=list, description="List of addresses associated with the warehouse")

class DetailedInboundShipment(BaseModel):
    """Model representing a detailed inbound shipment."""
    id: int = Field(..., description="Unique identifier for the shipment")
    created_at: datetime = Field(..., description="When the shipment was created")
    updated_at: datetime = Field(..., description="When the shipment was last updated")
    team_id: int = Field(..., description="ID of the team that owns the shipment")
    name: str = Field(..., description="Name of the shipment")
    notes: Optional[str] = Field(None, description="Notes about the shipment")
    warehouse_id: int = Field(..., description="ID of the warehouse")
    received_at: Optional[datetime] = Field(None, description="When the shipment was received")
    internal_notes: Optional[str] = Field(None, description="Internal notes about the shipment")
    archived_at: Optional[datetime] = Field(None, description="When the shipment was archived")
    shipped_at: Optional[datetime] = Field(None, description="When the shipment was shipped")
    checked_in_at: Optional[datetime] = Field(None, description="When the shipment was checked in")
    deleted_at: Optional[datetime] = Field(None, description="When the shipment was deleted")
    currency: str = Field(..., description="Currency code")
    eta: Optional[datetime] = Field(None, description="Estimated time of arrival")
    expected_quantity: int = Field(..., description="Expected quantity of items")
    sku_count: int = Field(..., description="Number of unique SKUs")
    shipment_id: Optional[int] = Field(None, description="External shipment ID")
    actual_quantity: int = Field(..., description="Actual quantity received")
    unsellable_quantity: int = Field(..., description="Quantity of unsellable items")
    received_quantity: int = Field(..., description="Total quantity received")
    reference_id: str = Field(..., description="Reference ID for the shipment")
    status: InboundShipmentStatus = Field(..., description="Current status of the shipment")
    tracking_numbers: List[TrackingNumber] = Field(..., description="List of tracking numbers")
    attachments: List[dict] = Field(..., description="List of attachments")
    service_lines: List[dict] = Field(..., description="List of service lines")
    warehouse: Warehouse = Field(..., description="Warehouse details")
    tags: List[str] = Field(..., description="List of tags")

class InboundShipmentResponse(BaseModel):
    """Response model for a specific inbound shipment."""
    shipment: DetailedInboundShipment = Field(..., description="The detailed shipment information")

class CreateInboundShipmentResponse(BaseModel):
    """Response model for creating an inbound shipment."""
    message: str = Field(..., description="Response message")
    shipment_id: int = Field(..., description="ID of the created shipment")

class UpdateInboundShipmentResponse(BaseModel):
    """Response model for updating an inbound shipment."""
    shipment: InboundShipment = Field(..., description="The updated shipment details")

class Carrier(str, Enum):
    """Valid carriers for inbound shipments."""
    CANADA_POST = "canada_post"
    DHL_EXPRESS = "dhl_express"
    FEDEX = "fedex"
    USPS = "usps"
    UPS = "ups"
    SHIPPO = "shippo"
    NO_TRACKING = "no_tracking"
    OTHER = "other"

class SubmitInboundShipmentResponse(BaseModel):
    """Response model for submitting an inbound shipment."""
    message: str = Field(..., description="Response message")

class ReceiveInboundShipmentResponse(BaseModel):
    """Response model for receiving an inbound shipment."""
    message: str = Field(..., description="Response message")

class BatchArchiveInboundShipmentsResponse(BaseModel):
    """Response model for batch archiving inbound shipments."""
    message: str = Field(..., description="Response message")

class RemoveItemFromShipmentResponse(BaseModel):
    """Response model for removing an item from an inbound shipment."""
    message: str = Field(..., description="Response message")

class AddItemToShipmentResponse(BaseModel):
    """Response model for adding an item to an inbound shipment."""
    message: str = Field(..., description="Response message")

class ShipmentItemExpected(BaseModel):
    """Model representing expected quantities for a shipment item."""
    quantity: int = Field(..., description="Expected quantity")
    item_group_configurations: List[dict] = Field(default_factory=list, description="Item group configurations")
    id: int = Field(..., description="ID of the expected record")

class ShipmentItemActual(BaseModel):
    """Model representing actual quantities for a shipment item."""
    quantity: int = Field(..., description="Actual quantity")
    item_group_configurations: List[dict] = Field(default_factory=list, description="Item group configurations")
    moves: List[dict] = Field(default_factory=list, description="Move records")
    id: int = Field(..., description="ID of the actual record")

class ShipmentItemUnsellable(BaseModel):
    """Model representing unsellable quantities for a shipment item."""
    quantity: int = Field(..., description="Unsellable quantity")

class ShipmentItem(BaseModel):
    """Model representing an item in a shipment."""
    id: int = Field(..., description="Unique identifier")
    item_id: int = Field(..., description="ID of the inventory item")
    shipment_id: int = Field(..., description="ID of the shipment")
    expected: ShipmentItemExpected = Field(..., description="Expected quantities")
    actual: ShipmentItemActual = Field(..., description="Actual quantities")
    unsellable: ShipmentItemUnsellable = Field(..., description="Unsellable quantities")
    item: InventoryItem = Field(..., description="The inventory item details")

class ShipmentItemsResponse(BaseModel):
    """Response model for getting items in an inbound shipment."""
    items: List[ShipmentItem] = Field(..., description="List of items in the shipment")

class OutboundShipmentStatus(str, Enum):
    """Possible statuses for an outbound shipment."""
    OPEN = "open"
    SHIPPED = "shipped"
    ARCHIVED = "archived"

class FBATransportPlan(BaseModel):
    """Model representing an FBA transport plan."""
    outbound_shipment_id: int = Field(..., description="ID of the outbound shipment")
    fba_shipment_id: str = Field(..., description="FBA shipment ID")
    fba_shipment_name: str = Field(..., description="FBA shipment name")
    fba_transport_v0_plan_id: str = Field(..., description="FBA transport plan ID")
    transport_status: str = Field(..., description="Transport status")

class OutboundShipment(BaseModel):
    """Model representing an outbound shipment."""
    id: int = Field(..., description="Unique identifier for the shipment")
    created_at: datetime = Field(..., description="When the shipment was created")
    updated_at: datetime = Field(..., description="When the shipment was last updated")
    team_id: int = Field(..., description="ID of the team that owns the shipment")
    status: OutboundShipmentStatus = Field(..., description="Current status of the shipment")
    notes: Optional[str] = Field(None, description="Notes about the shipment")
    name: str = Field(..., description="Name of the shipment")
    warehouse_id: int = Field(..., description="ID of the warehouse")
    shipped_at: Optional[datetime] = Field(None, description="When the shipment was shipped")
    internal_notes: Optional[str] = Field(None, description="Internal notes about the shipment")
    ship_from_address_id: Optional[int] = Field(None, description="ID of the shipping address")
    archived_at: Optional[datetime] = Field(None, description="When the shipment was archived")
    currency: str = Field(..., description="Currency code")
    is_case_forwarding: bool = Field(..., description="Whether this is a case forwarding shipment")
    sku_count: int = Field(..., description="Number of unique SKUs")
    shipped_items_count: Optional[int] = Field(None, description="Number of items shipped")
    searchable_identifiers: str = Field(..., description="Comma-separated list of searchable identifiers")
    searchable_tags: List[str] = Field(default_factory=list, description="List of searchable tags")
    tags: List[str] = Field(default_factory=list, description="List of tags")
    fba_transport_plans: List[FBATransportPlan] = Field(default_factory=list, description="List of FBA transport plans")

class OutboundShipmentsResponse(BaseModel):
    """Response model for outbound shipments with pagination."""
    current_page: int = Field(..., description="Current page number")
    data: List[OutboundShipment] = Field(..., description="List of outbound shipments")
    first_page_url: str = Field(..., description="URL for the first page")
    from_: Optional[int] = Field(None, alias="from", description="Starting index of the current page")
    last_page: int = Field(..., description="Last page number")
    last_page_url: str = Field(..., description="URL for the last page")
    links: List[PaginationLink] = Field(..., description="List of pagination links")
    next_page_url: Optional[str] = Field(None, description="URL for the next page")
    path: str = Field(..., description="Base path for the API endpoint")
    per_page: int = Field(..., description="Number of items per page")
    prev_page_url: Optional[str] = Field(None, description="URL for the previous page")
    to: Optional[int] = Field(None, description="Ending index of the current page")
    total: int = Field(..., description="Total number of items")

class ItemGroupConfigurationUpdate(BaseModel):
    """Model representing an item group configuration update."""
    configuration_id: int = Field(..., description="The configuration ID for the item group configuration")
    quantity: int = Field(..., description="The number of item groups")
    partial_quantity: int = Field(..., description="The extra items not included in a full item group")

class ExpectedItemUpdate(BaseModel):
    """Model representing expected item update."""
    quantity: int = Field(..., description="The quantity of the item that you are receiving in the shipment")
    item_group_configurations: List[ItemGroupConfigurationUpdate] = Field(..., description="Array of item group configurations")

class ActualItemUpdate(BaseModel):
    """Model representing actual item update."""
    quantity: int = Field(..., description="The quantity of the item that you have received in the shipment")
    item_group_configurations: List[ItemGroupConfigurationUpdate] = Field(..., description="Array of item group configurations")

class UpdateShipmentItemResponse(BaseModel):
    """Response model for updating an item in a shipment."""
    message: str = Field(..., description="Response message")

class DetailedOutboundShipment(BaseModel):
    """Model representing a detailed outbound shipment."""
    id: int = Field(..., description="Unique identifier for the shipment")
    created_at: datetime = Field(..., description="When the shipment was created")
    updated_at: datetime = Field(..., description="When the shipment was last updated")
    team_id: int = Field(..., description="ID of the team that owns the shipment")
    status: OutboundShipmentStatus = Field(..., description="Current status of the shipment")
    notes: Optional[str] = Field(None, description="Notes about the shipment")
    name: str = Field(..., description="Name of the shipment")
    warehouse_id: int = Field(..., description="ID of the warehouse")
    shipped_at: Optional[datetime] = Field(None, description="When the shipment was shipped")
    internal_notes: Optional[str] = Field(None, description="Internal notes about the shipment")
    errors: Optional[str] = Field(None, description="Any errors associated with the shipment")
    ship_from_address_id: Optional[int] = Field(None, description="ID of the shipping address")
    archived_at: Optional[datetime] = Field(None, description="When the shipment was archived")
    currency: str = Field(..., description="Currency code")
    is_case_forwarding: bool = Field(..., description="Whether this is a case forwarding shipment")
    is_case_packed: bool = Field(..., description="Whether this is a case packed shipment")
    outbound_items: List[OutboundShipmentItem] = Field(..., description="List of items in the shipment")
    service_lines: List[dict] = Field(default_factory=list, description="List of service lines")
    attachments: List[dict] = Field(default_factory=list, description="List of attachments")
    tags: List[str] = Field(default_factory=list, description="List of tags")

class OutboundShipmentResponse(BaseModel):
    """Response model for getting a specific outbound shipment."""
    shipment: DetailedOutboundShipment = Field(..., description="The detailed shipment information")

class CreateOutboundShipmentResponse(BaseModel):
    """Response model for creating an outbound shipment."""
    message: str = Field(..., description="Response message")
    shipment_id: int = Field(..., description="ID of the created shipment")

class ShipmentAttachment(BaseModel):
    """Model representing an attachment for a shipment."""
    id: int = Field(..., description="Unique identifier for the attachment")
    path: str = Field(..., description="Path to the attachment file")
    name: str = Field(..., description="Name of the attachment file")
    url: str = Field(..., description="URL to access the attachment")
    attachable_id: int = Field(..., description="ID of the entity the attachment belongs to")
    attachable_type: str = Field(..., description="Type of entity the attachment belongs to")
    created_at: datetime = Field(..., description="When the attachment was created")
    updated_at: datetime = Field(..., description="When the attachment was last updated")

class AddOutboundShipmentAttachmentResponse(BaseModel):
    """Response model for adding an attachment to an outbound shipment."""
    message: str = Field(..., description="Response message")
    attachments: List[ShipmentAttachment] = Field(..., description="List of attachments added to the shipment")

class AddOutboundShipmentItemResponse(BaseModel):
    """Response model for adding an item to an outbound shipment."""
    message: str = Field(..., description="Response message")

class UpdateOutboundShipmentItemResponse(BaseModel):
    """Response model for updating an outbound shipment item."""
    message: str = Field(..., description="Response message")

@dataclass
class OutboundShipmentItemUpdate:
    """Data class for updating an outbound shipment item."""
    quantity: Optional[int] = None
    item_group_configurations: Optional[List[ItemGroupConfigurationUpdate]] = None

class OrderStatus(str, Enum):
    """Possible statuses for an order."""
    PENDING = "pending"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    WAITING = "waiting"
    PICKED = "picked"

class Customer(BaseModel):
    """Model representing a customer."""
    id: int = Field(..., description="Unique identifier")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    name: str = Field(..., description="Customer name")
    team_id: int = Field(..., description="ID of the team")
    channel_id: int = Field(..., description="ID of the channel")
    default_address_id: int = Field(..., description="ID of the default address")
    email: str = Field(..., description="Customer email")
    phone_number: Union[str, None] = ""
    email_hash: str = Field(..., description="Hash of the customer email")
    name_address_hash: Union[str, None] = ""

class Item(BaseModel):
    """Model representing an inventory item."""
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    team_id: Optional[int] = None
    merchant_sku: Optional[str] = None
    title: Optional[str] = None
    sku: Optional[str] = ""
    name: Optional[str] = ""
    condition: Optional[str] = None
    condition_note: Optional[str] = None
    bundle_id: Optional[int] = None
    length_mm: Optional[int] = None
    width_mm: Optional[int] = None
    height_mm: Optional[int] = None
    weight_gm: Optional[int] = None
    quantity_in_stock: Optional[int] = 0
    available_quantity: Optional[int] = 0
    allocated_quantity: Optional[int] = 0
    unavailable_quantity: Optional[int] = 0
    inbound_quantity: Optional[int] = 0
    identifiers: List[Dict[str, Any]] = []

class OrderItem(BaseModel):
    """Model representing an item in an order."""
    item: Item
    quantity: int

class Order(BaseModel):
    """Model representing an order."""
    id: int
    status: OrderStatus = Field(..., description="Order status: pending, processing, shipped, cancelled, completed")
    created_at: datetime
    updated_at: datetime
    ship_by: Optional[datetime] = None
    arrive_by: Optional[datetime] = None
    should_fulfill: bool = True
    order_items_count: int = 0
    customer: Customer
    order_items: List[OrderItem] = []
    warehouse_notes: Optional[str] = None
    gift_notes: Optional[str] = None
    shipping_method_preferences: Optional[List[str]] = []
    quotes: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]] = None
    errors: Optional[List[str]] = []
    tags: List[str] = []

class OrdersResponse(BaseModel):
    """Response model for getting orders."""
    orders: List[Order]
    total: int = 0
    page: int = 1
    per_page: int = 50

class OrderResponse(BaseModel):
    """Response model for getting a specific order."""
    order: Order

class OrderItemUpload(BaseModel):
    """Model for an item in an order upload."""
    merchant_sku: str = Field(..., description="The SKU of the item matching. This should be consistent across all channels")
    quantity: int = Field(..., description="The quantity of this item that was ordered")
    title: Optional[str] = Field(None, description="The title of this item. This will only be used if the item does not already exist on the portal")

class OrderUpload(BaseModel):
    """Model for an order to be uploaded."""
    name: Optional[str] = Field(None, description="The name of the customer that placed the order. Required if first_name and last_name are not set.")
    first_name: Optional[str] = Field(None, description="The first name of the customer that placed the order. Required if name is not set.")
    last_name: Optional[str] = Field(None, description="The last name of the customer that placed the order. Required if name is not set.")
    email: Optional[str] = Field(None, description="The email address of the customer that placed the order.")
    phone: Optional[str] = Field(None, description="The phone number of the customer that placed the order.")
    address_line_1: str = Field(..., description="The first line of the shipping address for the customer that placed the order.")
    address_line_2: Optional[str] = Field(None, description="The second line of the shipping address for the customer that placed the order.")
    address_line_3: Optional[str] = Field(None, description="The third line of the shipping address for the customer that placed the order.")
    city: str = Field(..., description="The city of the shipping address for the customer that placed the order.")
    state_province: str = Field(..., description="The province or state of the shipping address for the customer that placed the order.")
    country: Optional[str] = Field(None, description="The country of the shipping address for the customer that placed the order. Required without country_code.")
    country_code: Optional[str] = Field(None, description="The country code of the shipping address for the customer that placed the order. Required without country.")
    postal_code: str = Field(..., description="The postal code / ZIP of the shipping address for the customer that placed the order.")
    is_residential: bool = Field(..., description="If the shipping address for the customer that placed the order is a residential address.")
    order_id: str = Field(..., description="A unique string that identifies this order")
    order_date: str = Field(..., description="The date this order was placed (YYYY-MM-DD)")
    gift_note: Optional[str] = Field(None, description="A gift note to be included with the order")
    items: List[OrderItemUpload] = Field(..., description="The items contained in the order")

class UploadOrdersResponse(BaseModel):
    """Response model for uploading orders."""
    message: str = Field(..., description="Response message from the API")

class Service(BaseModel):
    """Model representing a service offered at the warehouse."""
    id: int = Field(..., description="Unique identifier for the service")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")
    name: str = Field(..., description="Name of the service")
    type: str = Field(..., description="Type of the service")
    unit: str = Field(..., description="Unit of measurement for the service")
    when_to_charge: str = Field(..., description="When to charge for the service")
    charge: str = Field(..., description="Price per unit")
    advanced_options: Optional[Dict[str, Any]] = Field(None, description="Advanced options")
    service_provider_id: int = Field(..., description="ID of the service provider")
    price_records: List[Dict[str, Any]] = Field(default_factory=list, description="Price records")
    archived_at: Optional[str] = Field(None, description="When the service was archived")
    deleted_at: Optional[str] = Field(None, description="When the service was deleted")

class ServicesResponse(BaseModel):
    """Response model for getting a list of services."""
    services: List[Service] = Field(..., description="List of services")

class WarehousesResponse(BaseModel):
    """Response model for getting warehouses."""
    data: List[Warehouse] = Field(..., description="List of warehouses")

class AdjustmentReason(str, Enum):
    """Valid reasons for inventory adjustments."""
    LOST = "lost"
    FOUND = "found"
    DAMAGED = "damaged"
    OTHER = "other"

class AdjustmentMove(BaseModel):
    """Model representing a move associated with an adjustment."""
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")
    item_id: int = Field(..., description="ID of the affected item")
    sourced_at: Optional[str] = Field(None, description="When the item was sourced")
    sourced_by_user_id: Optional[int] = Field(None, description="ID of the user who sourced the item")
    arrived_at: Optional[str] = Field(None, description="When the item arrived")
    arrived_by_user_id: Optional[int] = Field(None, description="ID of the user who marked the item as arrived")
    quantity: int = Field(..., description="Adjustment quantity")
    notes: Optional[str] = Field(None, description="Notes for the move")
    reference_uuid: str = Field(..., description="Reference UUID for the adjustment")
    condition: Optional[str] = Field(None, description="Condition of the item")
    group_configuration_id: Optional[int] = Field(None, description="ID of the group configuration")
    uuid: str = Field(..., description="Unique UUID for the move")

class Adjustment(BaseModel):
    """Model representing an inventory adjustment."""
    notes: Optional[str] = Field(None, description="Notes explaining the reason for the adjustment")
    reason: AdjustmentReason = Field(..., description="Reason for the adjustment")
    warehouse_uuid: str = Field(..., description="UUID of the warehouse")
    uuid: str = Field(..., description="Unique UUID for the adjustment")
    created_at: str = Field(..., description="Creation timestamp")
    moves: List[AdjustmentMove] = Field(..., description="List of associated moves")

class CreateAdjustmentResponse(BaseModel):
    """Response model for creating an adjustment."""
    message: str = Field(..., description="Response message")
    adjustment: Adjustment = Field(..., description="The created adjustment")

class Merchant(BaseModel):
    """Model representing a merchant."""
    id: int = Field(..., description="Unique identifier for the merchant")
    name: str = Field(..., description="Merchant name")
    notes: Optional[str] = Field(None, description="Notes about the merchant")
    primaryEmail: str = Field(..., description="Primary email for the merchant")
    billingCycle: str = Field(..., description="Billing cycle (e.g., monthly)")
    perItemAdjustment: float = Field(..., description="Per item adjustment amount")
    photoUrl: Optional[str] = Field(None, description="URL to the merchant's photo")
    enabled: bool = Field(..., description="Whether the merchant is enabled")
    isOrdersEnabled: bool = Field(..., description="Whether orders are enabled for the merchant")
    isAmazonShipmentsEnabled: Optional[bool] = Field(None, description="Whether Amazon shipments are enabled")
    stripeCustomerId: Optional[str] = Field(None, description="Stripe customer ID")
    hasDefaultPaymentMethod: Optional[bool] = Field(None, description="Whether the merchant has a default payment method")
    pmLastFour: Optional[str] = Field(None, description="Last four digits of the payment method")
    billingAddress: Optional[str] = Field(None, description="Billing address")
    billingAddressLine2: Optional[str] = Field(None, description="Billing address line 2")
    billingCity: Optional[str] = Field(None, description="Billing city")
    billingState: Optional[str] = Field(None, description="Billing state")
    billingZip: Optional[str] = Field(None, description="Billing ZIP code")

class MerchantsResponse(BaseModel):
    """Response model for getting merchants."""
    data: List[Merchant] = Field(..., description="List of merchants")

class InvoiceWebhookTypes(BaseModel):
    """Model for invoice webhook types."""
    created: bool = Field(..., description="Notify when an invoice is created")

class InboundShipmentWebhookTypes(BaseModel):
    """Model for inbound shipment webhook types."""
    notes_updated: bool = Field(..., description="Notify when notes are updated")
    created: bool = Field(..., description="Notify when a shipment is created")
    shipped: bool = Field(..., description="Notify when a shipment is shipped")
    received: bool = Field(..., description="Notify when a shipment is received")

class OutboundShipmentWebhookTypes(BaseModel):
    """Model for outbound shipment webhook types."""
    notes_updated: bool = Field(..., description="Notify when notes are updated")
    created: bool = Field(..., description="Notify when a shipment is created")
    shipped: bool = Field(..., description="Notify when a shipment is shipped")
    closed: bool = Field(..., description="Notify when a shipment is closed")

class OrderWebhookTypes(BaseModel):
    """Model for order webhook types."""
    shipped: bool = Field(..., description="Notify when an order is shipped")

class WebhookTypes(BaseModel):
    """Model for webhook notification types."""
    invoice: InvoiceWebhookTypes = Field(..., description="Invoice notification settings")
    inbound_shipment: InboundShipmentWebhookTypes = Field(..., description="Inbound shipment notification settings")
    outbound_shipment: OutboundShipmentWebhookTypes = Field(..., description="Outbound shipment notification settings")
    order: OrderWebhookTypes = Field(..., description="Order notification settings")

class Webhook(BaseModel):
    """Model representing a webhook configuration."""
    id: int = Field(..., description="Unique identifier for the webhook")
    created_at: str = Field(..., alias="createdAt", description="When the webhook was created")
    updated_at: Optional[str] = Field(None, alias="updatedAt", description="When the webhook was last updated")
    url: str = Field(..., description="URL to send webhook notifications to")
    types: WebhookTypes = Field(..., description="Types of events to notify for")
    secret: str = Field(..., description="Secret key used to sign webhook payloads")
    
    class Config:
        populate_by_name = True

class WebhooksResponse(BaseModel):
    """Response model for getting webhooks."""
    webhooks: List[Webhook] = Field(..., description="List of webhooks")

class WebhookResponse(BaseModel):
    """Response model for creating or updating a webhook."""
    message: str = Field(..., description="Response message")
    webhook: Webhook = Field(..., description="The created or updated webhook")

class DeleteWebhookResponse(BaseModel):
    """Response model for deleting a webhook."""
    message: str = Field(..., description="Response message") 