"""
Models for eBay Catalog API.

This module defines the Pydantic models used for interacting with the eBay Catalog API,
specifically for searching product summaries by GTIN.
"""
from typing import Any, Dict, List, Optional
from pydantic import Field, field_validator

from ..base import EbayBaseModel, EbayResponse


class GTINSearchRequest(EbayBaseModel):
    """Request model for searching the eBay catalog by GTIN."""
    
    gtin: str = Field(
        ..., 
        description="The Global Trade Item Number (GTIN) to search for. Can be EAN, ISBN, or UPC.",
        example="0060935464"
    )
    marketplace_id: Optional[str] = Field(
        None,
        description="The eBay marketplace identifier. Default is EBAY_US if not specified.",
        examples=["EBAY_US", "EBAY_GB", "EBAY_DE"]
    )


class Image(EbayBaseModel):
    """Model for image data from the Catalog API."""
    
    height: Optional[int] = Field(None, description="The height of the image in pixels.")
    width: Optional[int] = Field(None, description="The width of the image in pixels.")
    image_url: str = Field(..., description="The URL of the image.", alias="imageUrl")


class Aspect(EbayBaseModel):
    """Model for category aspect data from the Catalog API."""
    
    localized_name: str = Field(..., description="The localized name of this category aspect.", alias="localizedName")
    localized_values: List[str] = Field(
        ..., 
        description="A list of the localized values of this category aspect.",
        alias="localizedValues"
    )


class ProductSummary(EbayBaseModel):
    """Model for a product summary from the Catalog API."""
    
    epid: str = Field(..., description="The eBay product ID of this product.")
    title: str = Field(..., description="The title of this product on eBay.")
    
    brand: Optional[str] = Field(None, description="The manufacturer's brand name for this product.")
    ean: Optional[List[str]] = Field(None, description="A list of all European Article Numbers (EANs) that identify this product.")
    upc: Optional[List[str]] = Field(None, description="A list of all Universal Product Codes (UPCs) that identify this product.")
    isbn: Optional[List[str]] = Field(None, description="A list of all International Standard Book Numbers (ISBNs) that identify this product.")
    gtin: Optional[List[str]] = Field(None, description="A list of all GTINs that identify this product. This includes EANs, ISBNs, and UPCs.")
    mpn: Optional[List[str]] = Field(None, description="A list of all Manufacturer Product Numbers that identify this product.")
    
    image: Optional[Image] = Field(None, description="The primary image of the product.")
    additional_images: Optional[List[Image]] = Field(
        None, 
        description="Additional images associated with this product.",
        alias="additionalImages"
    )
    
    aspects: Optional[List[Aspect]] = Field(
        None,
        description="An array of the category aspects and their values associated with this product."
    )
    
    product_href: Optional[str] = Field(
        None, 
        description="The URI of the getProduct call request that retrieves this product's details.",
        alias="productHref"
    )
    product_web_url: Optional[str] = Field(
        None, 
        description="The URL for this product's eBay product page.",
        alias="productWebUrl"
    )


class ProductSearchResult(EbayBaseModel):
    """Model for search results from the Catalog API."""
    
    href: Optional[str] = Field(None, description="The URI of the search method request that produced this result set.")
    total: Optional[int] = Field(None, description="The total number of matching products.")
    limit: Optional[int] = Field(None, description="The number of product summaries returned in the response.")
    
    product_summaries: Optional[List[ProductSummary]] = Field(
        None,
        description="An array of product summaries for products that match the search criteria.",
        alias="productSummaries"
    )


class CatalogSearchByGTINRequest(EbayBaseModel):
    """Request model for the search_by_gtin tool."""
    
    gtin: str = Field(
        ..., 
        description="The Global Trade Item Number (GTIN) to search for. Can be EAN, ISBN, or UPC.",
        example="0060935464"
    )
    
    @field_validator('gtin')
    @classmethod
    def validate_gtin(cls, v):
        """Validate that the GTIN is not empty."""
        if not v or not v.strip():
            raise ValueError("GTIN cannot be empty")
        return v


class CatalogSearchByGTINResponse(EbayBaseModel):
    """Response model for the search_by_gtin tool."""
    
    success: bool = Field(..., description="Whether the request was successful.")
    message: str = Field(..., description="A message describing the result of the operation.")
    status_code: Optional[int] = Field(None, description="The HTTP status code from the eBay API.")
    product_data: Optional[ProductSearchResult] = Field(
        None, 
        description="The product search results from the eBay API.",
        alias="productData"
    )
    
    @classmethod
    def success_response(cls, message: str, status_code: int, product_data: ProductSearchResult):
        """Create a successful response."""
        return cls(
            success=True,
            message=message,
            status_code=status_code,
            product_data=product_data
        )
    
    @classmethod
    def error_response(cls, message: str, status_code: Optional[int] = None):
        """Create an error response."""
        return cls(
            success=False,
            message=message,
            status_code=status_code,
            product_data=None
        )
