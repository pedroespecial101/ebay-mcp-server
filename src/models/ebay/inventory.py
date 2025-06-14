"""
Models for eBay Inventory API.

This module defines the actively-used Pydantic models only.
Legacy/unused models were removed on 2025-06-14.
"""

from typing import Any, Dict, List, Optional
from enum import Enum
from pydantic import Field, model_validator
from ..base import EbayBaseModel, EbayResponse

# -------------------------------------------------
# Offer models
# -------------------------------------------------

class UpdateOfferRequest(EbayBaseModel):
    """Full-replacement payload for the eBay updateOffer endpoint."""
    offer_id: str = Field(..., description="The unique identifier of the offer to update.")
    sku: Optional[str] = Field(None, max_length=50, description="The seller-defined SKU for the inventory item (≤50 chars).")
    marketplace_id: Optional[str] = Field(None, description="The eBay marketplace ID (e.g., EBAY_US, EBAY_GB).")
    format: Optional[str] = Field(None, description="Listing format. FIXED_PRICE (default) or AUCTION.")
    available_quantity: Optional[int] = Field(None, ge=0, description="Quantity available for purchase. Must be ≥1 for fixed-price; exactly 1 for auctions.")
    pricing_summary: Optional[Dict[str, Any]] = Field(None, description="Price container (price, MAP, strikethrough price). Required for published offers.")
    category_id: Optional[str] = Field(None, description="Primary eBay category ID. Required before publishing.")
    secondary_category_id: Optional[str] = Field(None, description="Secondary category ID for dual-category listings.")
    listing_description: Optional[str] = Field(None, max_length=500_000, description="HTML description of the listing (max 500k chars). Required before publishing.")
    listing_duration: Optional[str] = Field(None, description="Listing duration (e.g., 'GTC' for fixed price).")
    listing_start_date: Optional[str] = Field(None, description="Optional scheduled start time in UTC ISO format.")
    merchant_location_key: Optional[str] = Field(None, max_length=36, description="Merchant inventory location identifier (max 36 chars). Required before publishing.")
    listing_policies: Optional[Dict[str, Any]] = Field(None, description="Business policies container (payment, return, fulfilment). Required before publishing.")
    store_category_names: Optional[List[str]] = Field(None, max_items=2, description="eBay store category paths (max 2). Format: ['/Category/Subcategory']")
    quantity_limit_per_buyer: Optional[int] = Field(None, ge=1, description="Max quantity a single buyer can purchase across all transactions.")
    lot_size: Optional[int] = Field(None, ge=1, description="Number of items in a lot listing.")
    hide_buyer_details: Optional[bool] = Field(None, description="True for private listings that hide buyer IDs.")
    include_catalog_product_details: Optional[bool] = Field(None, description="Apply eBay catalog product details (defaults to True).")
    charity: Optional[Dict[str, Any]] = Field(None, description="Charitable organisation container.")
    extended_producer_responsibility: Optional[Dict[str, Any]] = Field(None, description="Eco-participation fee container (EPR).")
    regulatory: Optional[Dict[str, Any]] = Field(None, description="Regulatory information and compliance documents container.")
    tax: Optional[Dict[str, Any]] = Field(None, description="Tax configuration container.")

class ManageOfferAction(str, Enum):
    CREATE = "create"
    MODIFY = "modify"
    WITHDRAW = "withdraw"
    PUBLISH = "publish"
    GET = "get"

class OfferFormat(str, Enum):
    AUCTION = "AUCTION"
    FIXED_PRICE = "FIXED_PRICE"

class OfferDataForManage(EbayBaseModel):
    """Data payload for creating or modifying an offer. Fields are based on the eBay Offer object structure, using camelCase as per eBay API."""
    marketplaceId: Optional[str] = Field(None, description="This defaults to the marketplaceId set by the user and should not need to be changed.")
    format: Optional[OfferFormat] = Field(None, description="The listing format of the offer.")
    availableQuantity: Optional[int] = Field(None, ge=0, description="This integer value indicates the quantity of the inventory item (specified by the <strong>sku</strong> value) that will be available for purchase by buyers shopping on the eBay site specified in the <strong>marketplaceId</strong> field.")
    pricingSummary: Optional[Dict[str, Any]] = Field(None, description="Pricing information for the offer.", example={'price': {'value': '99.99', 'currency': 'GBP'}})
    categoryId: Optional[str] = Field(None, description="The unique identifier of the primary eBay category for the item. Use the 'get_category_suggestions' tool to find the appropriate category ID for your item. This field is required when creating a new offer.")
    listingDescription: Optional[str] = Field(None, max_length=500000, description="The description of the eBay listing that is part of the unpublished or published offer. This field is always returned for published offers, but is only returned if set for unpublished offers.<br><br><strong>Max Length</strong>: 500000 (which includes HTML markup/tags)")
    listingDuration: Optional[str] = Field(None, description="This defaults to the marketplaceId set by the user and should not need to be changed.")
    merchantLocationKey: Optional[str] = Field(None, max_length=36, description="This defaults to the marketplaceId set by the user and should not need to be changed.")
    listingPolicies: Optional[Dict[str, Any]] = Field(None, description="This defaults to the marketplaceId set by the user and should not need to be changed.")
    secondaryCategoryId: Optional[str] = Field(None, description="Rarely used")
    includeCatalogProductDetails: Optional[bool] = Field(None, description="This defaults to the marketplaceId set by the user and should not need to be changed.")
    class Config:
        validate_by_name = True

class ManageOfferToolInput(EbayBaseModel):
    sku: str = Field(..., description="Inventory item SKU.")
    action: ManageOfferAction = Field(..., description="Action to perform on the offer ('create', 'modify', 'withdraw', 'publish', 'get').")
    offer_data: Optional[OfferDataForManage] = Field(None, description="Data for create/modify actions. See OfferDataForManage schema.")
    @model_validator(mode='after')
    def check_offer_data_for_action(self):
        action = self.action
        offer_data = self.offer_data
        if action in [ManageOfferAction.CREATE, ManageOfferAction.MODIFY] and offer_data is None:
            raise ValueError("offer_data is required for 'create' or 'modify' actions.")
        if action in [ManageOfferAction.WITHDRAW, ManageOfferAction.PUBLISH, ManageOfferAction.GET] and offer_data is not None:
            raise ValueError(f"offer_data must NOT be provided for '{action.value}' action.")
        return self

class ManageOfferResponseDetails(EbayBaseModel):
    offer_id: Optional[str] = None
    status_code: Optional[int] = None
    message: str
    details: Optional[Any] = None # To store raw response from eBay if needed

class ManageOfferToolResponse(EbayResponse[ManageOfferResponseDetails]):
    pass

# -------------------------------------------------
# Inventory item management models
# -------------------------------------------------

class ShipToLocationAvailability(EbayBaseModel):
    """Quantity available for ship-to-home orders."""
    quantity: int = Field(
        ...,
        ge=0,
        title="Available Quantity",
        description=(
            "Total purchasable quantity of the inventory item for ship-to-home "
            "fulfilment. Must be greater than or equal to 0."
        ),
        examples=[10],
    )

class AvailabilityData(EbayBaseModel):
    """Top-level availability container (limited to shipToLocationAvailability)."""
    shipToLocationAvailability: ShipToLocationAvailability = Field(
        ...,
        title="Ship-To-Location Availability",
        description="Container for quantity available for domestic fulfilment instructions.",
    )

class ProductDataForInventoryItem(EbayBaseModel):
    """Product details container (limited-field version)."""
    title: str = Field(
        ...,
        max_length=80,
        title="Title",
        description="Title of the item exactly as it will appear on the eBay listing (max 80 characters).",
        examples=["Apple iPhone 15 Pro 256GB Natural Titanium"],
    )
    description: str = Field(
        ...,
        max_length=4000,
        title="Description",
        description="Full description of the product or lot in HTML or plain text (max 4000 characters).",
    )
    aspects: Optional[Dict[str, List[str]]] = Field(
        None,
        title="Aspects",
        description="Dictionary mapping aspect names (e.g. Colour, Size) to arrays of values. Must match category-specific allowed aspect names. Use the get_item_aspects_for_category MCP tool to retrieve the allowed and required aspect names for a specific category.",
        examples=[{"Colour": ["Black"], "Size": ["XL"]}],
    )
    brand: Optional[str] = Field(
        None,
        title="Brand",
        description="Brand or manufacturer of the item. If you know this, you can provide it, otherwise leave it out.",
        examples=["Apple"],
    )
    mpn: Optional[str] = Field(
        None,
        title="Manufacturer Part Number (MPN)",
        description="Manufacturer Part Number identifying the product.",
    )
    ean: Optional[List[str]] = Field(
        None,
        title="EAN List",
        description="Array of European Article Numbers associated with the product.",
        examples=[["190199098702"]],
    )
    upc: Optional[List[str]] = Field(
        None,
        title="UPC List",
        description="Array of Universal Product Codes associated with the product.",
        examples=[["190199098719"]],
    )
    isbn: Optional[List[str]] = Field(
        None,
        title="ISBN List",
        description="Array of International Standard Book Numbers associated with the product (books/media only).",
    )
    imageUrls: Optional[List[str]] = Field(
        None,
        title="Image URLs",
        description="Array of fully-qualified image URLs. First image is treated as the primary gallery image. If no image is provided use https://ebayimages.s3.us-east-005.backblazeb2.com/ebay_images/awaiting_image_holding.png. Warn the user that this image will be used if no image is provided.",
        examples=[
            [
                "https://example.com/image1.jpg",
                "https://example.com/image2.jpg",
                "https://example.com/image3.jpg",
            ]
        ],
    )
    class Config:
        validate_by_name = True

class ConditionEnum(str, Enum):
    NEW = "NEW"
    LIKE_NEW = "LIKE_NEW"
    NEW_OTHER = "NEW_OTHER"
    NEW_WITH_DEFECTS = "NEW_WITH_DEFECTS"
    USED_EXCELLENT = "USED_EXCELLENT"
    USED_VERY_GOOD = "USED_VERY_GOOD"
    USED_GOOD = "USED_GOOD"
    USED_ACCEPTABLE = "USED_ACCEPTABLE"
    FOR_PARTS_OR_NOT_WORKING = "FOR_PARTS_OR_NOT_WORKING"
    PRE_OWNED_EXCELLENT = "PRE_OWNED_EXCELLENT"
    PRE_OWNED_FAIR = "PRE_OWNED_FAIR"

class InventoryItemDataForManage(EbayBaseModel):
    """Data payload for creating or modifying an inventory item."""
    product: Optional[ProductDataForInventoryItem] = Field(
        None,
        title="Product Details",
        description="Container for title, description, identifiers and images of the product.",
    )
    condition: Optional[ConditionEnum] = Field(
        None,
        title="Condition",
        description=(
            "Enumeration value indicating the condition of the item. Must be one of "
            "the values in the Inventory API ConditionEnum (e.g. NEW, USED_GOOD, "
            "MANUFACTURER_REFURBISHED)."
        ),
        examples=[ConditionEnum.NEW, ConditionEnum.USED_GOOD],
    )
    conditionDescription: Optional[str] = Field(
        None,
        title="Condition Description",
        description=(
            "More detailed, human-readable condition notes. Allowed for all "
            "conditions other than brand-new. Ignored by eBay if provided with a "
            "new condition."
        ),
    )
    availability: Optional[AvailabilityData] = Field(
        None,
        title="Availability",
        description="Container defining quantity available for purchase.",
    )
    class Config:
        validate_by_name = True

class ManageInventoryItemAction(str, Enum):
    CREATE = "create"
    MODIFY = "modify"
    GET = "get"
    DELETE = "delete"

class ManageInventoryItemToolInput(EbayBaseModel):
    sku: str = Field(..., description="Inventory item SKU.", max_length=50)
    action: ManageInventoryItemAction = Field(..., description="Action to perform on the inventory item ('create', 'modify', 'get', 'delete').")
    item_data: Optional[InventoryItemDataForManage] = Field(None, description="Data for create/modify actions. See InventoryItemDataForManage schema.")
    @model_validator(mode='after')
    def check_item_data_for_action(self):
        action = self.action
        item_data = self.item_data
        if action in [ManageInventoryItemAction.CREATE, ManageInventoryItemAction.MODIFY] and item_data is None:
            raise ValueError("item_data is required for 'create' or 'modify' actions.")
        if action in [ManageInventoryItemAction.GET, ManageInventoryItemAction.DELETE] and item_data is not None:
            raise ValueError(f"item_data must NOT be provided for '{action.value}' action.")
        return self

class ManageInventoryItemResponseDetails(EbayBaseModel):
    sku: Optional[str] = None
    status_code: Optional[int] = None
    message: str
    details: Optional[Any] = None # To store raw response from eBay if needed

class ManageInventoryItemToolResponse(EbayResponse[ManageInventoryItemResponseDetails]):
    pass

# -------------------------------------------------
# Inventory item list models
# -------------------------------------------------

class InventoryItemDetails(EbayBaseModel):
    sku: str = Field(..., description="Seller-defined SKU.")
    locale: Optional[str] = Field(None, description="Locale of the inventory item.")
    condition: Optional[str] = Field(None, description="Condition code of the item.")
    condition_description: Optional[str] = Field(None, description="Free-text description elaborating on the condition.")
    package_weight_and_size: Optional[Dict[str, Any]] = Field(None, description="Package weight & dimensions.")
    product: Optional[Dict[str, Any]] = Field(None, description="Product data such as title, aspects, etc.")
    availability: Optional[Dict[str, Any]] = Field(None, description="Quantity information for the item.")
    group_ids: Optional[List[str]] = Field(None, description="Inventory item group IDs the item belongs to.")

class InventoryItemsListResponse(EbayBaseModel):
    inventory_items: List[InventoryItemDetails] = Field(default_factory=list, description="List of inventory items.")
    total: Optional[int] = Field(None, description="Total number of inventory items.")
    size: Optional[int] = Field(None, description="Number of items in this response.")
    offset: Optional[int] = Field(None, description="Pagination offset.")
    limit: Optional[int] = Field(None, description="Pagination limit.")
    href: Optional[str] = Field(None, description="URL of this page of results.")
    next: Optional[str] = Field(None, description="URL of the next page of results.")
    prev: Optional[str] = Field(None, description="URL of the previous page of results.")
    @classmethod
    def success_response(cls, data: Dict[str, Any]):
        items = [
            InventoryItemDetails(
                sku=item.get("sku", ""),
                locale=item.get("locale"),
                condition=item.get("condition"),
                condition_description=item.get("conditionDescription"),
                package_weight_and_size=item.get("packageWeightAndSize"),
                product=item.get("product"),
                availability=item.get("availability"),
                group_ids=item.get("groupIds", []),
            )
            for item in data.get("inventoryItems", [])
        ]
        return cls(
            inventory_items=items,
            total=data.get("total"),
            size=data.get("size"),
            offset=data.get("offset"),
            limit=data.get("limit"),
            href=data.get("href"),
            next=data.get("next"),
            prev=data.get("prev"),
        )
    @classmethod
    def error_response(cls, error_message: str):
        return cls(inventory_items=[], total=0, size=0)
