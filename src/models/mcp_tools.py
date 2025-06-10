"""
Models for MCP tool parameters and responses.
"""
from typing import Any, Dict, List, Optional, Union
from pydantic import Field, field_validator, model_validator
from .base import EbayBaseModel, EbayResponse


class AddToolParams(EbayBaseModel):
    """Parameters for the add tool."""
    
    a: int = Field(..., description="First number to add.")
    b: int = Field(..., description="Second number to add.")
    
    @field_validator('a', 'b')
    def validate_numbers(cls, v):
        """Validate that the numbers are integers."""
        if not isinstance(v, int):
            raise ValueError(f"Value must be an integer, got {type(v)}")
        return v


class AddToolResponse(EbayResponse[int]):
    """Response for the add tool."""
    pass


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


class OfferBySkuParams(EbayBaseModel):
    """Parameters for the get_offer_by_sku tool."""
    
    sku: str = Field(..., description="The seller-defined SKU (Stock Keeping Unit) of the offer.")


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

    # Offer identification: Provide EITHER offer_id OR sku.
    offer_id: Optional[str] = Field(
        None,
        description="The unique identifier of the offer to update. Provide either this or SKU."
    )

    sku: Optional[str] = Field(
        None,
        max_length=50,
        description="The seller-defined SKU. Provide either this or Offer ID. Max length: 50 characters."
    )

    @model_validator(mode='before')
    @classmethod
    def check_offer_id_or_sku_provided(cls, data: Any) -> Any:
        """Ensure that exactly one of offer_id or sku is provided."""
        if isinstance(data, dict):
            offer_id = data.get('offer_id')
            sku = data.get('sku')

            if offer_id is not None and sku is not None:
                raise ValueError("Provide exactly one of offer_id or sku, not both.")
            if offer_id is None and sku is None:
                raise ValueError("Either offer_id or sku must be provided to identify the offer.")
        return data

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


class ListingFeesParams(EbayBaseModel):
    """Parameters for the get_listing_fees tool."""
    
    offer_ids: List[str] = Field(..., description="List of offer IDs to get fees for (up to 250).")
    
    @field_validator('offer_ids')
    def validate_offer_ids(cls, v):
        """Validate the length of the offer_ids list."""
        if len(v) > 250:
            raise ValueError("Maximum of 250 offer IDs allowed")
        return v


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


class GetInventoryItemBySkuParams(EbayBaseModel):
    """Parameters for the get_inventory_item_by_sku tool."""

    sku: str = Field(..., description="The seller-defined SKU (Stock Keeping Unit) of the inventory item to retrieve.")

    @field_validator('sku')
    def validate_sku(cls, v):
        """Convert the SKU to string if needed and validate length."""
        sku_str = str(v) if v is not None else v
        if sku_str and len(sku_str) > 50:
            raise ValueError("SKU must be 50 characters or less")
        return sku_str


class GetInventoryItemsParams(EbayBaseModel):
    """Parameters for the get_inventory_items tool."""

    limit: int = Field(25, description="The maximum number of inventory items to return per page (1-200).")
    offset: int = Field(0, description="The number of inventory items to skip before starting to return results.")

    @field_validator('limit')
    def validate_limit(cls, v):
        """Validate that limit is within acceptable range."""
        if v < 1 or v > 200:
            raise ValueError("Limit must be between 1 and 200")
        return v

    @field_validator('offset')
    def validate_offset(cls, v):
        """Validate that offset is non-negative."""
        if v < 0:
            raise ValueError("Offset must be non-negative")
        return v


class DeleteInventoryItemParams(EbayBaseModel):
    """Parameters for the delete_inventory_item tool."""

    sku: str = Field(..., description="The seller-defined SKU (Stock Keeping Unit) of the inventory item to delete.")

    @field_validator('sku')
    def validate_sku(cls, v):
        """Convert the SKU to string if needed and validate length."""
        sku_str = str(v) if v is not None else v
        if sku_str and len(sku_str) > 50:
            raise ValueError("SKU must be 50 characters or less")
        return sku_str


class CreateOrReplaceInventoryItemParams(EbayBaseModel):
    """Parameters for the create_or_replace_inventory_item tool."""

    sku: str = Field(..., description="The seller-defined SKU (Stock Keeping Unit) of the inventory item.")
    condition: str = Field(..., description="The condition of the inventory item.")
    product_title: str = Field(..., description="The title of the product.")
    product_description: str = Field(..., description="The description of the product.")
    quantity: int = Field(1, description="The quantity available for the inventory item.")
    product_aspects: Optional[Dict[str, Any]] = Field(None, description="Product aspects as key-value pairs.")
    product_imageUrls: Optional[List[str]] = Field(None, description="List of image URLs for the product.")
    product_brand: Optional[str] = Field(None, description="The brand of the product.")
    product_mpn: Optional[str] = Field(None, description="The manufacturer part number.")
    product_ean: Optional[List[str]] = Field(None, description="List of EAN codes.")
    product_upc: Optional[List[str]] = Field(None, description="List of UPC codes.")
    product_isbn: Optional[List[str]] = Field(None, description="List of ISBN codes.")
    product_epid: Optional[str] = Field(None, description="The eBay product identifier.")
    product_subtitle: Optional[str] = Field(None, description="The subtitle of the product.")
    product_videoIds: Optional[List[str]] = Field(None, description="List of video IDs for the product.")
    condition_description: Optional[str] = Field(None, description="Additional description of the item condition.")
    condition_descriptors: Optional[List[Dict[str, Any]]] = Field(None, description="List of condition descriptors.")
    package_weight_value: Optional[float] = Field(None, description="The weight value of the package.")
    package_weight_unit: Optional[str] = Field(None, description="The weight unit of the package.")
    package_dimensions_length: Optional[float] = Field(None, description="The length of the package.")
    package_dimensions_width: Optional[float] = Field(None, description="The width of the package.")
    package_dimensions_height: Optional[float] = Field(None, description="The height of the package.")
    package_dimensions_unit: Optional[str] = Field(None, description="The dimension unit of the package.")
    package_type: Optional[str] = Field(None, description="The package type.")
    package_shipping_irregular: Optional[bool] = Field(None, description="Whether the package has irregular shipping.")
    availability_distributions: Optional[List[Dict[str, Any]]] = Field(None, description="Availability distributions.")
    pickup_availability: Optional[List[Dict[str, Any]]] = Field(None, description="Pickup availability information.")

    @field_validator('sku')
    def validate_sku(cls, v):
        """Convert the SKU to string if needed and validate length."""
        sku_str = str(v) if v is not None else v
        if not sku_str or len(sku_str.strip()) == 0:
            raise ValueError("SKU cannot be empty")
        if len(sku_str) > 50:
            raise ValueError("SKU must be 50 characters or less")
        return sku_str.strip()

    @field_validator('condition')
    def validate_condition(cls, v):
        """Validate condition against eBay's allowed values."""
        allowed_conditions = [
            'NEW', 'LIKE_NEW', 'NEW_OTHER', 'NEW_WITH_DEFECTS',
            'MANUFACTURER_REFURBISHED', 'CERTIFIED_REFURBISHED',
            'EXCELLENT_REFURBISHED', 'VERY_GOOD_REFURBISHED',
            'GOOD_REFURBISHED', 'SELLER_REFURBISHED',
            'USED_EXCELLENT', 'USED_VERY_GOOD', 'USED_GOOD',
            'USED_ACCEPTABLE', 'FOR_PARTS_OR_NOT_WORKING',
            'PRE_OWNED_EXCELLENT', 'PRE_OWNED_FAIR'
        ]
        if v not in allowed_conditions:
            raise ValueError(f"Condition must be one of: {', '.join(allowed_conditions)}")
        return v

    @field_validator('product_title')
    def validate_product_title(cls, v):
        """Validate product title is not empty."""
        if not v or len(v.strip()) == 0:
            raise ValueError("Product title cannot be empty")
        return v.strip()

    @field_validator('product_description')
    def validate_product_description(cls, v):
        """Validate product description is not empty."""
        if not v or len(v.strip()) == 0:
            raise ValueError("Product description cannot be empty")
        return v.strip()

    @field_validator('quantity')
    def validate_quantity(cls, v):
        """Validate quantity is positive."""
        if v < 1:
            raise ValueError("Quantity must be at least 1")
        return v

    @field_validator('product_imageUrls')
    def validate_image_urls(cls, v):
        """Validate image URLs format."""
        if v is not None:
            import re
            url_pattern = re.compile(
                r'^https?://'  # http:// or https://
                r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
                r'localhost|'  # localhost...
                r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
                r'(?::\d+)?'  # optional port
                r'(?:/?|[/?]\S+)$', re.IGNORECASE)

            for url in v:
                if not url_pattern.match(url):
                    raise ValueError(f"Invalid URL format: {url}")
        return v

    @field_validator('package_weight_unit')
    def validate_weight_unit(cls, v):
        """Validate weight unit."""
        if v is not None:
            allowed_units = ['POUND', 'KILOGRAM', 'OUNCE', 'GRAM']
            if v not in allowed_units:
                raise ValueError(f"Weight unit must be one of: {', '.join(allowed_units)}")
        return v

    @field_validator('package_dimensions_unit')
    def validate_dimensions_unit(cls, v):
        """Validate dimensions unit."""
        if v is not None:
            allowed_units = ['INCH', 'FEET', 'CENTIMETER', 'METER']
            if v not in allowed_units:
                raise ValueError(f"Dimensions unit must be one of: {', '.join(allowed_units)}")
        return v
