"""
Models for eBay Inventory API.

This module defines the actively-used Pydantic models only.
Legacy/unused models were removed on 2025-06-14.
"""

from typing import Any, Dict, List, Optional

from pydantic import Field

from ..base import EbayBaseModel

# -------------------------------------------------
# Offer models
# -------------------------------------------------

# Used by src/ebay_mcp/inventory/manage_offer.py
class UpdateOfferRequest(EbayBaseModel):
    """Full-replacement payload for the eBay updateOffer endpoint."""

    # Core identification
    offer_id: str = Field(..., description="The unique identifier of the offer to update.")
    sku: Optional[str] = Field(
        None, max_length=50, description="The seller-defined SKU for the inventory item (≤50 chars)."
    )
    marketplace_id: Optional[str] = Field(
        None, description="The eBay marketplace ID (e.g., EBAY_US, EBAY_GB)."
    )
    format: Optional[str] = Field(
        None, description="Listing format. FIXED_PRICE (default) or AUCTION."
    )

    # Inventory & availability
    available_quantity: Optional[int] = Field(
        None,
        ge=0,
        description="Quantity available for purchase. Must be ≥1 for fixed-price; exactly 1 for auctions.",
    )

    # Pricing (required when publishing an offer)
    pricing_summary: Optional[Dict[str, Any]] = Field(
        None,
        description="Price container (price, MAP, strikethrough price). Required for published offers.",
    )

    # Categories
    category_id: Optional[str] = Field(
        None, description="Primary eBay category ID. Required before publishing."
    )
    secondary_category_id: Optional[str] = Field(
        None, description="Secondary category ID for dual-category listings."
    )

    # Listing content
    listing_description: Optional[str] = Field(
        None,
        max_length=500_000,
        description="HTML description of the listing (max 500k chars). Required before publishing.",
    )
    listing_duration: Optional[str] = Field(
        None, description="Listing duration (e.g., 'GTC' for fixed price)."
    )
    listing_start_date: Optional[str] = Field(
        None, description="Optional scheduled start time in UTC ISO format."
    )

    # Fulfilment
    merchant_location_key: Optional[str] = Field(
        None,
        max_length=36,
        description="Merchant inventory location identifier (max 36 chars). Required before publishing.",
    )

    # Business policies
    listing_policies: Optional[Dict[str, Any]] = Field(
        None,
        description="Business policies container (payment, return, fulfilment). Required before publishing.",
    )

    # Store
    store_category_names: Optional[List[str]] = Field(
        None,
        max_items=2,
        description="eBay store category paths (max 2). Format: ['/Category/Subcategory']",
    )

    # Purchase limits & special features
    quantity_limit_per_buyer: Optional[int] = Field(
        None, ge=1, description="Max quantity a single buyer can purchase across all transactions."
    )
    lot_size: Optional[int] = Field(
        None, ge=1, description="Number of items in a lot listing."
    )
    hide_buyer_details: Optional[bool] = Field(
        None, description="True for private listings that hide buyer IDs."
    )
    include_catalog_product_details: Optional[bool] = Field(
        None, description="Apply eBay catalog product details (defaults to True)."
    )

    # Charity & compliance
    charity: Optional[Dict[str, Any]] = Field(
        None, description="Charitable organisation container."
    )
    extended_producer_responsibility: Optional[Dict[str, Any]] = Field(
        None, description="Eco-participation fee container (EPR)."
    )
    regulatory: Optional[Dict[str, Any]] = Field(
        None, description="Regulatory information and compliance documents container."
    )

    # Tax
    tax: Optional[Dict[str, Any]] = Field(
        None, description="Tax configuration container."
    )


# -------------------------------------------------
# Inventory item list models
# -------------------------------------------------

class InventoryItemDetails(EbayBaseModel):
    """Subset of the InventoryItem schema returned by eBay."""

    sku: str = Field(..., description="Seller-defined SKU.")
    locale: Optional[str] = Field(None, description="Locale of the inventory item.")
    condition: Optional[str] = Field(None, description="Condition code of the item.")
    condition_description: Optional[str] = Field(
        None, description="Free-text description elaborating on the condition."
    )
    package_weight_and_size: Optional[Dict[str, Any]] = Field(
        None, description="Package weight & dimensions."
    )
    product: Optional[Dict[str, Any]] = Field(
        None, description="Product data such as title, aspects, etc."
    )
    availability: Optional[Dict[str, Any]] = Field(
        None, description="Quantity information for the item."
    )
    group_ids: Optional[List[str]] = Field(
        None, description="Inventory item group IDs the item belongs to."
    )


class InventoryItemsListResponse(EbayBaseModel):
    """API wrapper for a list of inventory items."""

    inventory_items: List[InventoryItemDetails] = Field(
        default_factory=list, description="List of inventory items."
    )
    total: Optional[int] = Field(None, description="Total number of inventory items.")
    size: Optional[int] = Field(None, description="Number of items in this response.")
    offset: Optional[int] = Field(None, description="Pagination offset.")
    limit: Optional[int] = Field(None, description="Pagination limit.")
    href: Optional[str] = Field(None, description="URL of this page of results.")
    next: Optional[str] = Field(None, description="URL of the next page of results.")
    prev: Optional[str] = Field(None, description="URL of the previous page of results.")

    # Helper constructors
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
