"""
Models for MCP tool parameters and responses.
"""
from typing import Any, Dict, List, Optional, Union
from pydantic import Field, field_validator
from .base import EbayBaseModel, EbayResponse


class SearchEbayItemsParams(EbayBaseModel):
    """Parameters for the search_ebay_items tool."""
    
    query: str = Field(..., description="The search query string.")
    limit: int = Field(10, description="The maximum number of items to return.")
    
    @field_validator('limit')
    def validate_limit(cls, v):
        """Validate that limit is a positive integer."""
        if v <= 0:
            raise ValueError("Limit must be a positive integer")
        return v


class CategorySuggestionsParams(EbayBaseModel):
    """Parameters for the get_category_suggestions tool."""
    
    query: str = Field(..., description="The query string to find category suggestions for.")
    
    @field_validator("query")
    @classmethod
    def validate_query(cls, value):
        """Ensure query is a string, even if a numeric value is provided."""
        if value is not None and not isinstance(value, str):
            return str(value)
        return value


class ItemAspectsParams(EbayBaseModel):
    """
Parameters for the get_item_aspects_for_category tool."""
    
    category_id: str = Field(..., description="The eBay category ID to get aspects for.")
    
    @field_validator('category_id')
    def validate_category_id(cls, v):
        """Convert the category_id to string if it's an integer."""
        return str(v) if v is not None else v


class UpdateOfferParams(EbayBaseModel):
    """
    Parameters for the update_offer tool.

    ⚠️  CRITICAL WARNING: This is a REPLACE operation! ⚠️

    The updateOffer API call performs a COMPLETE REPLACEMENT of the existing offer object.
    ALL current offer data will be overwritten with the provided values. Any fields not
    included in the update request will be cleared/reset to defaults.

    RECOMMENDED WORKFLOW:
    1. First call the Get Offer tool to retrieve current offer data
    2. Modify only the desired fields while preserving all other existing values
    3. Include ALL existing field values in the update request to prevent data loss

    For published offers, certain fields become required and must be provided.
    """

    # Required fields
    offer_id: str = Field(
        ...,
        description="The unique identifier of the offer to update. This is required to identify which offer to modify."
    )

    # Core offer identification (conditionally required)
    sku: Optional[str] = Field(
        None,
        max_length=50,
        description="The seller-defined SKU (Stock Keeping Unit) of the offer. Max length: 50 characters. Required if not already set in the offer."
    )

    marketplace_id: Optional[str] = Field(
        None,
        description="The eBay marketplace ID (e.g., EBAY_US, EBAY_GB, EBAY_DE). Required if not already set in the offer."
    )

    # Inventory and pricing
    available_quantity: Optional[int] = Field(
        None,
        ge=0,
        description="The quantity of the inventory item available for purchase. Must be 1 or more for purchasable items. For auction listings, must be 1."
    )

    pricing_summary: Optional[Dict[str, Any]] = Field(
        None,
        description="Container for listing price and pricing features (MAP, Strikethrough Pricing). Required for published offers and before publishing unpublished offers."
    )

    # Listing details
    category_id: Optional[str] = Field(
        None,
        description="The unique identifier of the eBay category. Required before publishing an offer. Use Taxonomy API getCategorySuggestions to find category IDs."
    )

    listing_description: Optional[str] = Field(
        None,
        max_length=500000,
        description="The description of the eBay listing. Required for published offers. Supports HTML markup. Max length: 500,000 characters including HTML."
    )

    listing_duration: Optional[str] = Field(
        None,
        description="Number of days the listing will be active. For fixed-price listings, must be 'GTC' (Good 'Til Cancelled). Required before publishing."
    )

    listing_start_date: Optional[str] = Field(
        None,
        description="Future timestamp (UTC format) when listing becomes active. Format: YYYY-MM-DDTHH:MM:SSZ (e.g., 2023-05-30T19:08:00Z). Optional for scheduled listings."
    )

    # Location and policies
    merchant_location_key: Optional[str] = Field(
        None,
        max_length=36,
        description="Unique identifier of the merchant's inventory location. Required before publishing an offer. Max length: 36 characters."
    )

    listing_policies: Optional[Dict[str, Any]] = Field(
        None,
        description="Container for business policies (payment, return, fulfillment) and custom policies. Required for published offers and before publishing."
    )

    # Additional listing features
    secondary_category_id: Optional[str] = Field(
        None,
        description="Unique identifier for a secondary category. Optional dual-category listing (fees may apply). Not available for US eBay Motors vehicles."
    )

    store_category_names: Optional[List[str]] = Field(
        None,
        max_items=2,
        description="Array of eBay store category paths (max 2). Format: ['/Fashion/Men/Shirts', '/Fashion/Men/Accessories']. Only for sellers with eBay stores."
    )

    quantity_limit_per_buyer: Optional[int] = Field(
        None,
        ge=1,
        description="Maximum quantity each buyer can purchase. Limits cumulative purchases across multiple transactions. Must be 1 or greater if specified."
    )

    lot_size: Optional[int] = Field(
        None,
        ge=1,
        description="Total number of items in a lot listing (e.g., set of 4 tires). Only applicable for lot listings. Must be 1 or greater."
    )

    # Special features and compliance
    hide_buyer_details: Optional[bool] = Field(
        None,
        description="Set to true to create a private listing where buyer IDs and feedback scores are obfuscated from other users."
    )

    include_catalog_product_details: Optional[bool] = Field(
        None,
        description="Whether to apply eBay product catalog details to the listing. Defaults to true if omitted. Set to false to disable catalog integration."
    )

    charity: Optional[Dict[str, Any]] = Field(
        None,
        description="Container for charitable organization details. Includes charityId and donationPercentage for listings that donate sale proceeds to charity."
    )

    extended_producer_responsibility: Optional[Dict[str, Any]] = Field(
        None,
        description="Container for eco-participation fee information. Required in some markets (e.g., France) for environmental compliance."
    )

    regulatory: Optional[Dict[str, Any]] = Field(
        None,
        description="Container for regulatory information and compliance documents. May be required for certain product categories or markets (e.g., GPSR in EU)."
    )

    tax: Optional[Dict[str, Any]] = Field(
        None,
        description="Container for sales tax, VAT, or tax exception settings. Required if tax information currently exists for the offer."
    )

    @field_validator('offer_id')
    def validate_offer_id(cls, v):
        """Convert the offer_id to string if it's an integer."""
        return str(v) if v is not None else v

    @field_validator('sku')
    def validate_sku(cls, v):
        """Validate SKU length constraints."""
        if v is not None and len(v) > 50:
            raise ValueError("SKU must be 50 characters or less")
        return v

    @field_validator('available_quantity')
    def validate_available_quantity(cls, v):
        """Validate available quantity is non-negative."""
        if v is not None and v < 0:
            raise ValueError("Available quantity must be 0 or greater")
        return v

    @field_validator('quantity_limit_per_buyer')
    def validate_quantity_limit_per_buyer(cls, v):
        """Validate quantity limit per buyer is positive."""
        if v is not None and v < 1:
            raise ValueError("Quantity limit per buyer must be 1 or greater")
        return v

    @field_validator('lot_size')
    def validate_lot_size(cls, v):
        """Validate lot size is positive."""
        if v is not None and v < 1:
            raise ValueError("Lot size must be 1 or greater")
        return v

    @field_validator('merchant_location_key')
    def validate_merchant_location_key(cls, v):
        """Validate merchant location key length."""
        if v is not None and len(v) > 36:
            raise ValueError("Merchant location key must be 36 characters or less")
        return v

    @field_validator('listing_description')
    def validate_listing_description(cls, v):
        """Validate listing description length."""
        if v is not None and len(v) > 500000:
            raise ValueError("Listing description must be 500,000 characters or less")
        return v

    @field_validator('store_category_names')
    def validate_store_category_names(cls, v):
        """Validate store category names array."""
        if v is not None and len(v) > 2:
            raise ValueError("Maximum of 2 store category names allowed")
        return v
    



class WithdrawOfferParams(EbayBaseModel):
    """
Parameters for the withdraw_offer tool."""
    
    offer_id: str = Field(..., description="The unique identifier of the offer to withdraw.")
    
    @field_validator('offer_id')
    def validate_offer_id(cls, v):
        """Convert the offer_id to string if it's an integer."""
        return str(v) if v is not None else v


class TestAuthResponse(EbayResponse[str]):
    """Response for the test_auth tool."""
    
    token_prefix: Optional[str] = Field(None, description="First 50 characters of the token.")
    token_length: Optional[int] = Field(None, description="Length of the token.")
    error_message: Optional[str] = Field(None, description="Error message if token acquisition failed.")
    
    @classmethod
    def success_response(cls, token: str):
        """Create a success response with token information."""
        return cls(
            status="success",
            data=f"Token found (first 50 chars): {token[:50]}...\nToken length: {len(token)}",
            token_prefix=token[:50],
            token_length=len(token)
        )
    
    @classmethod
    def error_response(cls, error_message: str):
        """Create an error response with the error message."""
        return cls(
            status="error",
            error_message=error_message,
            data=f"Token acquisition failed. Details: {error_message}"
        )


class TriggerEbayLoginResponse(EbayResponse[str]):
    """Response for the trigger_ebay_login tool."""

    user_name: Optional[str] = Field(None, description="eBay user name if login was successful.")
    error_details: Optional[str] = Field(None, description="Error details if login failed.")

    @classmethod
    def success_response(cls, user_name: str):
        """Create a success response with the user name."""
        return cls(
            status="success",
            data=f"eBay login process completed successfully. The user '{user_name}' has been authenticated with eBay and can now use the eBay API tools.",
            user_name=user_name
        )

    @classmethod
    def error_response(cls, error_message: str, error_details: str = "No specific error details provided."):
        """Create an error response with error message and details."""
        return cls(
            status="error",
            data=f"eBay login process failed. Error: {error_message}. Details: {error_details}. Please check server logs.",
            error_message=error_message,
            error_details=error_details
        )

    @classmethod
    def uncertain_response(cls, login_result: Any):
        """Create a response for uncertain login outcome."""
        return cls(
            status="unknown",
            data="eBay login process finished. The outcome is unclear. Please check server logs.",
            debug_info=str(login_result)
        )


class GetInventoryItemsParams(EbayBaseModel):
    """Parameters for the get_inventory_items tool."""
    
    limit: int = Field(25, description="The maximum number of inventory items to return per page (1-200).")
    offset: int = Field(0, description="The number of inventory items to skip before starting to return results.")
    
    @field_validator('limit')
    @classmethod
    def validate_limit(cls, v):
        """Validate that limit is within acceptable range."""
        if v < 1 or v > 200:
            raise ValueError("Limit must be between 1 and 200")
        return v
    
    @field_validator('offset')
    @classmethod
    def validate_offset(cls, v):
        """Validate that offset is non-negative."""
        if v < 0:
            raise ValueError("Offset cannot be negative")
        return v
