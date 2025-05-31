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
