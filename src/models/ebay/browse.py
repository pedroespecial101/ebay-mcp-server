"""
Models for eBay Browse API.
"""
from typing import Any, Dict, List, Optional
from pydantic import Field
from ..base import EbayBaseModel, EbayResponse


class ItemSummary(EbayBaseModel):
    """Model for an item summary from the Browse API."""
    
    item_id: str = Field(..., description="The eBay identifier of the item.")
    title: str = Field(..., description="The title of the item.")
    image_url: Optional[str] = Field(None, description="URL to the primary image of the item.")
    price: Optional[Dict[str, Any]] = Field(None, description="The price of the item.")
    seller: Optional[Dict[str, Any]] = Field(None, description="Information about the seller.")
    condition: Optional[str] = Field(None, description="The condition of the item.")
    item_web_url: Optional[str] = Field(None, description="The URL to the item's web page on eBay.")
    

class SearchResult(EbayBaseModel):
    """Model for search results from the Browse API."""
    
    total: int = Field(..., description="The total number of items found.")
    items: List[ItemSummary] = Field(default_factory=list, description="List of items found.")
    href: Optional[str] = Field(None, description="The URL to the current result set.")
    next_page: Optional[str] = Field(None, description="The URL to the next page of results.")
    prev_page: Optional[str] = Field(None, description="The URL to the previous page of results.")
    limit: Optional[int] = Field(None, description="The number of items per page.")
    offset: Optional[int] = Field(None, description="The offset of the current page.")


class SearchRequest(EbayBaseModel):
    """Model for search request parameters."""
    
    query: str = Field(..., description="The search query string.")
    limit: int = Field(10, description="The number of items to return per page.")
    
    
# Response wrappers
SearchResponse = EbayResponse[SearchResult]
