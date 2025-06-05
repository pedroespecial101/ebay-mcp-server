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
    """Model for updating an offer."""
    
    offer_id: str = Field(..., description="The unique identifier of the offer to update.")
    sku: str = Field(..., description="The seller-defined SKU of the offer.")
    marketplace_id: str = Field("EBAY_GB", description="The eBay marketplace ID.")
    format: str = Field("FIXED_PRICE", description="The listing format.")
    available_quantity: Optional[int] = Field(None, description="The quantity available for the offer.")
    category_id: Optional[str] = Field(None, description="The primary category ID for the offer.")
    listing_policies: Optional[Dict[str, Any]] = Field(None, description="The listing policies for the offer.")
    merchant_location_key: Optional[str] = Field(None, description="The merchant location key.")
    pricing_summary: Optional[Dict[str, Any]] = Field(None, description="Pricing information for the offer.")
    inventory_location: Optional[str] = Field(None, description="The inventory location.")
    listing_description: Optional[str] = Field(None, description="The description of the listing.")
    listing_status: Optional[str] = Field(None, description="The status of the listing.")
    tax: Optional[Dict[str, Any]] = Field(None, description="Tax information for the offer.")
    listing_id: Optional[str] = Field(None, description="The eBay listing ID if published.")


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


class InventoryItemResponse(EbayResponse[InventoryItemDetails]):
    """Response model for inventory item details."""
    pass


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


class DeleteInventoryItemResponse(EbayBaseModel):
    """Response model for delete inventory item operation."""

    success: bool = Field(..., description="Whether the deletion was successful.")
    message: str = Field(..., description="Success or error message.")
    sku: Optional[str] = Field(None, description="The SKU that was deleted.")

    @classmethod
    def success_response(cls, sku: str):
        """Create a success response for deletion."""
        return cls(
            success=True,
            message=f"Inventory item with SKU '{sku}' has been successfully deleted.",
            sku=sku
        )

    @classmethod
    def error_response(cls, error_message: str, sku: str = None):
        """Create an error response for deletion."""
        return cls(
            success=False,
            message=f"Failed to delete inventory item: {error_message}",
            sku=sku
        )


class CreateOrReplaceInventoryItemRequest(EbayBaseModel):
    """Request model for create or replace inventory item operation."""

    availability: Optional[Dict[str, Any]] = Field(None, description="Availability information including quantity.")
    condition: str = Field(..., description="The condition of the inventory item.")
    condition_description: Optional[str] = Field(None, description="Additional description of the item condition.")
    condition_descriptors: Optional[List[Dict[str, Any]]] = Field(None, description="List of condition descriptors.")
    package_weight_and_size: Optional[Dict[str, Any]] = Field(None, description="Package weight and dimensions.")
    product: Dict[str, Any] = Field(..., description="Product details including title, description, aspects, etc.")

    @classmethod
    def from_params(cls, params):
        """Create request from validated parameters."""
        # Build product object
        product = {
            "title": params.product_title,
            "description": params.product_description
        }

        # Add optional product fields
        if params.product_aspects:
            product["aspects"] = params.product_aspects
        if params.product_imageUrls:
            product["imageUrls"] = params.product_imageUrls
        if params.product_brand:
            product["brand"] = params.product_brand
        if params.product_mpn:
            product["mpn"] = params.product_mpn
        if params.product_ean:
            product["ean"] = params.product_ean
        if params.product_upc:
            product["upc"] = params.product_upc
        if params.product_isbn:
            product["isbn"] = params.product_isbn
        if params.product_epid:
            product["epid"] = params.product_epid
        if params.product_subtitle:
            product["subtitle"] = params.product_subtitle
        if params.product_videoIds:
            product["videoIds"] = params.product_videoIds

        # Build availability object
        availability = {
            "shipToLocationAvailability": {
                "quantity": params.quantity
            }
        }

        # Add availability distributions if provided
        if params.availability_distributions:
            availability["shipToLocationAvailability"]["availabilityDistributions"] = params.availability_distributions

        # Add pickup availability if provided
        if params.pickup_availability:
            availability["pickupAtLocationAvailability"] = params.pickup_availability

        # Build package weight and size if provided
        package_weight_and_size = None
        if any([params.package_weight_value, params.package_dimensions_length,
                params.package_dimensions_width, params.package_dimensions_height]):
            package_weight_and_size = {}

            if params.package_weight_value and params.package_weight_unit:
                package_weight_and_size["weight"] = {
                    "value": params.package_weight_value,
                    "unit": params.package_weight_unit
                }

            if any([params.package_dimensions_length, params.package_dimensions_width,
                    params.package_dimensions_height]):
                dimensions = {}
                if params.package_dimensions_length:
                    dimensions["length"] = params.package_dimensions_length
                if params.package_dimensions_width:
                    dimensions["width"] = params.package_dimensions_width
                if params.package_dimensions_height:
                    dimensions["height"] = params.package_dimensions_height
                if params.package_dimensions_unit:
                    dimensions["unit"] = params.package_dimensions_unit

                if dimensions:
                    package_weight_and_size["dimensions"] = dimensions

            if params.package_type:
                package_weight_and_size["packageType"] = params.package_type
            if params.package_shipping_irregular is not None:
                package_weight_and_size["shippingIrregular"] = params.package_shipping_irregular

        # Build condition descriptors if provided
        condition_descriptors = None
        if params.condition_descriptors:
            condition_descriptors = params.condition_descriptors

        return cls(
            availability=availability,
            condition=params.condition,
            condition_description=params.condition_description,
            condition_descriptors=condition_descriptors,
            package_weight_and_size=package_weight_and_size,
            product=product
        )


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
