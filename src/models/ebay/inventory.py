"""
Models for eBay Inventory API.
"""
from typing import Any, Dict, List, Optional, Union
from pydantic import Field, root_validator
from datetime import datetime
from ..base import EbayBaseModel, EbayResponse


class OfferPriceQuantity(EbayBaseModel):
    """Model for price and quantity information in an offer."""
    
    price: Dict[str, Any] = Field(..., description="The price details of the offer.")
    quantity: int = Field(..., description="The quantity available for the offer.")


class OfferDetails(EbayBaseModel):
    """Model for offer details."""
    
    offer_id: str = Field(..., description="The unique identifier of the offer.")
    sku: str = Field(..., description="The seller-defined Stock Keeping Unit (SKU).")
    marketplace_id: str = Field(..., description="The eBay marketplace ID (e.g., EBAY_GB).")
    format: str = Field(..., description="The listing format (e.g., FIXED_PRICE).")
    available_quantity: int = Field(..., description="The quantity available for the offer.")
    price: Dict[str, Any] = Field(..., description="The price details of the offer.")
    listing_description: Optional[str] = Field(None, description="The description of the listing.")
    listing_policies: Optional[Dict[str, Any]] = Field(None, description="The listing policies for the offer.")
    listing_status: Optional[str] = Field(None, description="The status of the listing.")
    tax: Optional[Dict[str, Any]] = Field(None, description="Tax information for the offer.")
    category_id: Optional[str] = Field(None, description="The primary category ID for the offer.")


class OfferRequest(EbayBaseModel):
    """Model for offer request parameters."""
    
    sku: str = Field(..., description="The seller-defined Stock Keeping Unit (SKU).")


class OfferResponse(EbayResponse[OfferDetails]):
    """Response model for offer details."""
    pass


class UpdateOfferRequest(EbayBaseModel):
    """
    Model for updating an offer via eBay Inventory API updateOffer endpoint.

    ⚠️  CRITICAL: This is a COMPLETE REPLACEMENT operation! ⚠️

    The updateOffer API performs a full replacement of the existing offer object.
    ALL current offer data will be overwritten. Any fields not included will be
    cleared/reset to defaults.

    Based on EbayOfferDetailsWithId schema from eBay Sell Inventory v1 API.
    """

    # Core identification (these are typically preserved from current offer)
    offer_id: str = Field(..., description="The unique identifier of the offer to update.")
    sku: Optional[str] = Field(None, max_length=50, description="The seller-defined SKU. Max length: 50.")
    marketplace_id: Optional[str] = Field(None, description="The eBay marketplace ID (e.g., EBAY_US, EBAY_GB).")
    format: Optional[str] = Field(None, description="The listing format (FIXED_PRICE or AUCTION).")

    # Inventory and availability
    available_quantity: Optional[int] = Field(
        None,
        ge=0,
        description="Quantity available for purchase. Must be 1+ for purchasable items, exactly 1 for auctions."
    )

    # Pricing (required for published offers)
    pricing_summary: Optional[Dict[str, Any]] = Field(
        None,
        description="Pricing container with price, MAP, and strikethrough pricing. Required for published offers."
    )

    # Categories
    category_id: Optional[str] = Field(
        None,
        description="Primary eBay category ID. Required before publishing an offer."
    )

    secondary_category_id: Optional[str] = Field(
        None,
        description="Secondary category ID for dual-category listings. Fees may apply."
    )

    # Listing content
    listing_description: Optional[str] = Field(
        None,
        max_length=500000,
        description="Listing description. Required for published offers. Supports HTML. Max: 500,000 chars."
    )

    listing_duration: Optional[str] = Field(
        None,
        description="Listing duration. 'GTC' for fixed-price, various options for auctions. Required before publishing."
    )

    listing_start_date: Optional[str] = Field(
        None,
        description="Scheduled start time in UTC format (YYYY-MM-DDTHH:MM:SSZ). Optional."
    )

    # Location and fulfillment
    merchant_location_key: Optional[str] = Field(
        None,
        max_length=36,
        description="Merchant inventory location identifier. Required before publishing. Max: 36 chars."
    )

    # Business policies (required for published offers)
    listing_policies: Optional[Dict[str, Any]] = Field(
        None,
        description="Business policies container (payment, return, fulfillment). Required for published offers."
    )

    # Store integration
    store_category_names: Optional[List[str]] = Field(
        None,
        max_items=2,
        description="eBay store category paths. Max 2 categories. Format: ['/Category/Subcategory']."
    )

    # Purchase restrictions and special features
    quantity_limit_per_buyer: Optional[int] = Field(
        None,
        ge=1,
        description="Maximum quantity per buyer across all transactions. Must be 1+."
    )

    lot_size: Optional[int] = Field(
        None,
        ge=1,
        description="Number of items in lot listing. For multi-item lots only."
    )

    hide_buyer_details: Optional[bool] = Field(
        None,
        description="True for private listings (obfuscated buyer IDs)."
    )

    include_catalog_product_details: Optional[bool] = Field(
        None,
        description="Apply eBay catalog product details. Defaults to true if omitted."
    )

    # Charitable and compliance features
    charity: Optional[Dict[str, Any]] = Field(
        None,
        description="Charitable organization container with charityId and donationPercentage."
    )

    extended_producer_responsibility: Optional[Dict[str, Any]] = Field(
        None,
        description="Eco-participation fee container. Required in some markets (e.g., France)."
    )

    regulatory: Optional[Dict[str, Any]] = Field(
        None,
        description="Regulatory information and compliance documents container."
    )

    # Tax settings
    tax: Optional[Dict[str, Any]] = Field(
        None,
        description="Tax configuration container (sales tax, VAT, exceptions)."
    )


class WithdrawOfferRequest(EbayBaseModel):
    """Model for withdrawing an offer."""
    
    offer_id: str = Field(..., description="The unique identifier of the offer to withdraw.")


class ListingFeeRequest(EbayBaseModel):
    """Model for listing fee request."""
    
    offers: List[Dict[str, str]] = Field(..., description="List of offer objects containing offer IDs to get fees for (up to 250).")


class Fee(EbayBaseModel):
    """Model for a fee."""
    
    amount: Dict[str, Any] = Field(..., description="The amount of the fee.")
    fee_type: str = Field(..., description="The type of fee.")


class OfferFees(EbayBaseModel):
    """Model for fees associated with an offer."""
    
    offer_id: str = Field(..., description="The unique identifier of the offer.")
    fees: List[Fee] = Field(default_factory=list, description="List of fees for the offer.")


class ListingFeeResponse(EbayBaseModel):
    """Response model for listing fees."""

    fees: List[Dict[str, Any]] = Field(default_factory=list, description="List of fee summaries for each offer.")
    warnings: List[Dict[str, Any]] = Field(default_factory=list, description="Any warnings returned by the API.")

    @classmethod
    def success_response(cls, data):
        """Create a success response with fees data."""
        return cls(fees=data, warnings=[])

    @classmethod
    def error_response(cls, error_message: str):
        """Create an error response."""
        return cls(fees=[], warnings=[{"message": error_message}])


class InventoryItemDetails(EbayBaseModel):
    """Model for inventory item details."""

    sku: str = Field(..., description="The seller-defined Stock Keeping Unit (SKU).")
    locale: Optional[str] = Field(None, description="The locale for the inventory item.")
    condition: Optional[str] = Field(None, description="The condition of the inventory item.")
    condition_description: Optional[str] = Field(None, description="Additional description of the item condition.")
    package_weight_and_size: Optional[Dict[str, Any]] = Field(None, description="Package weight and dimensions.")
    product: Optional[Dict[str, Any]] = Field(None, description="Product details including title, description, aspects, etc.")
    availability: Optional[Dict[str, Any]] = Field(None, description="Availability information including quantity.")
    group_ids: Optional[List[str]] = Field(None, description="List of inventory item group IDs this item belongs to.")





class InventoryItemsListResponse(EbayBaseModel):
    """Response model for inventory items list."""

    inventory_items: List[InventoryItemDetails] = Field(default_factory=list, description="List of inventory items.")
    total: Optional[int] = Field(None, description="Total number of inventory items.")
    size: Optional[int] = Field(None, description="Number of items in this response.")
    offset: Optional[int] = Field(None, description="Offset used for pagination.")
    limit: Optional[int] = Field(None, description="Limit used for pagination.")
    href: Optional[str] = Field(None, description="URL for this page of results.")
    next: Optional[str] = Field(None, description="URL for the next page of results.")
    prev: Optional[str] = Field(None, description="URL for the previous page of results.")

    @classmethod
    def success_response(cls, data: Dict[str, Any]):
        """Create a success response with inventory items data."""
        inventory_items = []
        if 'inventoryItems' in data:
            for item in data['inventoryItems']:
                inventory_items.append(InventoryItemDetails(
                    sku=item.get('sku', ''),
                    locale=item.get('locale'),
                    condition=item.get('condition'),
                    condition_description=item.get('conditionDescription'),
                    package_weight_and_size=item.get('packageWeightAndSize'),
                    product=item.get('product'),
                    availability=item.get('availability'),
                    group_ids=item.get('groupIds', [])
                ))

        return cls(
            inventory_items=inventory_items,
            total=data.get('total'),
            size=data.get('size'),
            offset=data.get('offset'),
            limit=data.get('limit'),
            href=data.get('href'),
            next=data.get('next'),
            prev=data.get('prev')
        )

    @classmethod
    def error_response(cls, error_message: str):
        """Create an error response."""
        return cls(inventory_items=[], total=0, size=0)


class CreateOrReplaceInventoryItemResponse(EbayBaseModel):
    """Response model for create or replace inventory item operation."""

    success: bool = Field(..., description="Whether the operation was successful.")
    message: str = Field(..., description="Success or error message.")
    sku: Optional[str] = Field(None, description="The SKU that was created or updated.")
    operation: Optional[str] = Field(None, description="Whether the item was 'created' or 'updated'.")
    status_code: Optional[int] = Field(None, description="HTTP status code from the API.")

    @classmethod
    def success_response(cls, sku: str, status_code: int):
        """Create a success response for create/replace operation."""
        operation = "created" if status_code == 201 else "updated"
        return cls(
            success=True,
            message=f"Inventory item with SKU '{sku}' has been successfully {operation}.",
            sku=sku,
            operation=operation,
            status_code=status_code
        )

    @classmethod
    def error_response(cls, error_message: str, sku: str = None, status_code: int = None):
        """Create an error response for create/replace operation."""
        return cls(
            success=False,
            message=f"Failed to create or replace inventory item: {error_message}",
            sku=sku,
            operation=None,
            status_code=status_code
        )
