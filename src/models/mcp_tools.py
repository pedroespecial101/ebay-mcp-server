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


# --- The legacy UpdateOfferParams and WithdrawOfferParams classes were removed in the Pydantic v2 refactor ---


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
