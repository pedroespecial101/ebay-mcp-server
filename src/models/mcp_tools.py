"""
Models for MCP tool parameters and responses.
"""
from typing import Any, Dict, List, Optional, Union
from pydantic import Field, field_validator
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
Parameters for the update_offer tool."""
    
    offer_id: str = Field(..., description="The unique identifier of the offer to update.")
    sku: str = Field(..., description="The seller-defined SKU of the offer.")
    marketplace_id: str = Field("EBAY_GB", description="The eBay marketplace ID.")
    price: Optional[float] = Field(None, description="New price for the offer.")
    available_quantity: Optional[int] = Field(None, description="New quantity for the offer.")
    
    @field_validator('offer_id')
    def validate_offer_id(cls, v):
        """Convert the offer_id to string if it's an integer."""
        return str(v) if v is not None else v
    
    @field_validator('sku')
    def validate_sku(cls, v):
        """Convert the SKU to string if needed."""
        return str(v) if v is not None else v
    
    @field_validator('price')
    def validate_price(cls, v):
        """Validate that price is positive if provided."""
        if v is not None and float(v) <= 0:
            raise ValueError("Price must be a positive number")
        return float(v) if v is not None else v
    
    @field_validator('available_quantity')
    def validate_quantity(cls, v):
        """Validate that quantity is non-negative if provided."""
        if v is not None and int(v) < 0:
            raise ValueError("Available quantity must be a non-negative integer")
        return int(v) if v is not None else v


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
