"""
Models for eBay Inventory API.

This module defines the actively-used Pydantic models only.
Legacy/unused models were removed on 2025-06-14.
"""

from typing import Any, Dict, List, Optional
from enum import Enum
from pydantic import Field, model_validator
from pydantic.alias_generators import to_camel
from ..base import EbayBaseModel, EbayResponse

# Reusable field definition for SKU to adhere to DRY principle.
sku_field = Field(
    ...,
    description="Seller-defined Stock Keeping Unit for the inventory item.",
    max_length=50,
    alias="sku"
)

# -------------------------------------------------
# Offer models
# -------------------------------------------------

class ManageOfferAction(str, Enum):
    CREATE = "create"
    MODIFY = "modify"
    WITHDRAW = "withdraw"
    PUBLISH = "publish"
    GET = "get"

class OfferFormat(str, Enum):
    AUCTION = "AUCTION"
    FIXED_PRICE = "FIXED_PRICE"

class OfferDataForLLM(EbayBaseModel):
    """Data payload for an eBay offer, containing only fields intended for LLM interaction.
    All fields are optional to allow sparse updates for MODIFY actions.
    For CREATE, required fields are enforced by the tool's internal logic after merging defaults.
    """
    # format: Optional[OfferFormat] = Field(
    #     None,
    #     title="Listing Format",
    #     description=(
    #         "The format of the eBay listing. Must be one of the OfferFormat enum values: "
    #         f"{', '.join([e.value for e in OfferFormat])}. "
    #         "AUCTION for auction-style listings or FIXED_PRICE for Buy It Now listings."
    #     ),
    #     examples=[OfferFormat.FIXED_PRICE, OfferFormat.AUCTION],
    # )
    available_quantity: Optional[int] = Field(
        None,
        ge=0,
        title="Available Quantity",
        description=(
            "The quantity of the inventory item (specified by SKU) that will be "
            "available for purchase on the specified marketplace."
        ),
        examples=[5],
    )
    pricing_summary: Optional[Dict[str, Any]] = Field(
        None,
        title="Pricing Summary",
        description=(
            "Container for pricing information including price and currency. "
            "For example: {'price': {'value': '99.99', 'currency': 'GBP'}}"
        ),
        examples=[{'price': {'value': '99.99', 'currency': 'GBP'}}],
    )
    category_id: Optional[str] = Field(
        None,
        title="Primary Category ID",
        description=(
            "The unique identifier of the primary eBay category for the item. "
            "Required when creating a new offer. Use the 'get_category_suggestions' "
            "tool to find the appropriate category ID."
        ),
        examples=["9355"],
    )
    # listing_description: Optional[str] = Field(
    #     None,
    #     max_length=500000,
    #     title="Listing Description",
    #     description=(
    #         "The HTML or plain text description of the eBay listing. "
    #         "Maximum length is 500,000 characters including HTML markup/tags. "
    #         "Always returned for published offers, only returned if set for unpublished offers."
    #     ),
    # )
    # secondary_category_id: Optional[str] = Field(
    #     None,
    #     title="Secondary Category ID",
    #     description=(
    #         "The unique identifier of the secondary eBay category for the item. "
    #         "Optional and rarely used in most listing scenarios."
    #     ),
    # )

    class Config:
        alias_generator = to_camel
        populate_by_name = True

class OfferDataForManage(OfferDataForLLM):
    """Data payload for creating or modifying an eBay offer (Full model for API interaction).

    These are not passed the the LLM, but are used to create the final payload for API calls.

    This model extends OfferDataForLLM with additional fields required for direct API calls,
    which are typically populated from system defaults rather than direct LLM input.
    """
    marketplace_id: Optional[str] = Field(
        None,
        title="Marketplace ID",
        description=(
            "The ID of the eBay marketplace where the offer will be listed. "
            "Defaults to the marketplaceId set in the user's configuration."
        ),
    )
    listing_duration: Optional[str] = Field(
        None,
        title="Listing Duration",
        description=(
            "The length of time the listing will be active on eBay. "
            "Defaults to the marketplace's standard duration if not specified."
        ),
        examples=["GTC"],  # Good 'Til Cancelled
    )
    merchant_location_key: Optional[str] = Field(
        None,
        max_length=36,
        title="Merchant Location Key",
        description=(
            "The unique identifier of the merchant's location where the item is stored. "
            "Defaults to the primary location if not specified."
        ),
    )
    listing_policies: Optional[Dict[str, Any]] = Field(
        None,
        title="Listing Policies",
        description=(
            "Container for various listing policies including return policy, payment policy, "
            "and fulfillment policy. If not provided, eBay will use the seller's default policies."
        ),
    )
    include_catalog_product_details: Optional[bool] = Field(
        None,
        title="Include Catalog Product Details",
        description=(
            "If true, eBay will include catalog product details in the listing. "
            "Defaults to true for items listed with an eBay catalog product."
        ),
    )

    class Config(OfferDataForLLM.Config):  # Inherit Config as well
        pass

class ManageOfferToolInput(EbayBaseModel):
    sku: str = sku_field
    action: ManageOfferAction = Field(..., description="Action to perform on the offer ('create', 'modify', 'withdraw', 'publish', 'get').")
    offer_data: Optional[OfferDataForLLM] = Field(None, description="Data for create/modify actions. See OfferDataForLLM schema for available fields.")
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
    offer_id: Optional[str] = Field(None, alias="offerId")
    status_code: Optional[int] = Field(None, alias="statusCode")
    message: str
    details: Optional[Any] = None # To store raw response from eBay if needed

    class Config:
        populate_by_name = True

class ManageOfferToolResponse(EbayResponse[ManageOfferResponseDetails]):
    pass

# -------------------------------------------------
# Inventory item management models
# -------------------------------------------------

class ShipToLocationAvailability(EbayBaseModel):
    """Quantity available for ship-to-home orders."""
    quantity: Optional[int] = Field(
        None,
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
    ship_to_location_availability: Optional[ShipToLocationAvailability] = Field(
        None,
        alias="shipToLocationAvailability",
        title="Ship-To-Location Availability",
        description="Container for quantity available for domestic fulfilment instructions.",
    )
    class Config:
        populate_by_name = True

class ProductDataForInventoryItem(EbayBaseModel):
    """Product details container (limited-field version)."""
    title: Optional[str] = Field(
        None,
        max_length=80,
        title="Title",
        description="Title of the item exactly as it will appear on the eBay listing (max 80 characters).",
        examples=["Apple iPhone 17 Pro 256GB Natural Titanium"],
    )
    description: Optional[str] = Field(
        None,
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
        description="Array of European Article Numbers associated with the product. Great if you know it - don't worry if not.",
        examples=[["190199098702"]],
    )
    upc: Optional[List[str]] = Field(
        None,
        title="UPC List",
        description="Array of Universal Product Codes associated with the product. Great if you know it - don't worry if not.",
        examples=[["190199098719"]],
    )
    isbn: Optional[List[str]] = Field(
        None,
        title="ISBN List",
        description="Array of International Standard Book Numbers associated with the product (books/media only). Pretty important if you're selling books, so try and find it!",
    )
    image_urls: Optional[List[str]] = Field(
        None,
        alias="imageUrls",
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
        populate_by_name = True

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
    condition_description: Optional[str] = Field(
        None,
        alias="conditionDescription",
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
        populate_by_name = True

class ManageInventoryItemAction(str, Enum):
    CREATE = "create"
    MODIFY = "modify"
    GET = "get"
    DELETE = "delete"

class ManageInventoryItemToolInput(EbayBaseModel):
    sku: str = sku_field
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
    status_code: Optional[int] = Field(None, alias="statusCode")
    message: str
    details: Optional[Any] = None # To store raw response from eBay if needed

    class Config:
        populate_by_name = True

class ManageInventoryItemToolResponse(EbayResponse[ManageInventoryItemResponseDetails]):
    pass

# -------------------------------------------------
# Inventory item list models
# -------------------------------------------------

class InventoryItemDetails(EbayBaseModel):
    sku: str = Field(..., description="Seller-defined SKU.")
    locale: Optional[str] = Field(None, description="Locale of the inventory item.")
    condition: Optional[str] = Field(None, description="Condition code of the item.")
    condition_description: Optional[str] = Field(None, alias="conditionDescription", description="Free-text description elaborating on the condition.")
    package_weight_and_size: Optional[Dict[str, Any]] = Field(None, alias="packageWeightAndSize", description="Package weight & dimensions.")
    product: Optional[Dict[str, Any]] = Field(None, description="Product data such as title, aspects, etc.")
    availability: Optional[Dict[str, Any]] = Field(None, description="Quantity information for the item.")
    group_ids: Optional[List[str]] = Field(None, alias="groupIds", description="Inventory item group IDs the item belongs to.")

    class Config:
        populate_by_name = True

class InventoryItemsListResponse(EbayBaseModel):
    inventory_items: List[InventoryItemDetails] = Field(default_factory=list, alias="inventoryItems", description="List of inventory items.")
    total: Optional[int] = Field(None, description="Total number of inventory items.")
    size: Optional[int] = Field(None, description="Number of items in this response.")
    offset: Optional[int] = Field(None, description="Pagination offset.")
    limit: Optional[int] = Field(None, description="Pagination limit.")
    href: Optional[str] = Field(None, description="URL of this page of results.")
    next: Optional[str] = Field(None, description="URL of the next page of results.")
    prev: Optional[str] = Field(None, description="URL of the previous page of results.")

    class Config:
        populate_by_name = True

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
