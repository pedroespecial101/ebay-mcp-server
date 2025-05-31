"""
Models for eBay Taxonomy API.
"""
from typing import Any, Dict, List, Optional
from pydantic import Field
from ..base import EbayBaseModel, EbayResponse


class CategorySuggestion(EbayBaseModel):
    """Model for a category suggestion from the Taxonomy API."""
    
    category_id: str = Field(..., description="The eBay category ID.")
    category_name: str = Field(..., description="The name of the category.")
    category_tree_node_level: Optional[int] = Field(None, description="The level of the category in the tree.")
    relevancy: Optional[float] = Field(None, description="A relevancy score for the category.")
    category_tree_id: Optional[str] = Field(None, description="The ID of the category tree.")
    leaf_category: Optional[bool] = Field(None, description="Whether this is a leaf category.")


class CategorySuggestionRequest(EbayBaseModel):
    """Model for category suggestion request parameters."""
    
    query: str = Field(..., description="The query string to find category suggestions for.")


class CategorySuggestionResponse(EbayResponse[List[CategorySuggestion]]):
    """Response model for category suggestions."""
    pass


class AspectValue(EbayBaseModel):
    """Model for an aspect value."""
    
    value: str = Field(..., description="The value of the aspect.")
    value_constraints: Optional[List[str]] = Field(None, description="Constraints on the value.")


class Aspect(EbayBaseModel):
    """Model for an item aspect."""
    
    aspect_name: str = Field(..., description="The name of the aspect.")
    aspect_values: List[AspectValue] = Field(default_factory=list, description="Possible values for the aspect.")
    aspect_constraint: Optional[str] = Field(None, description="Constraint type of the aspect.")
    cardinality: Optional[str] = Field(None, description="Cardinality of the aspect (SINGLE/MULTIPLE).")
    required: Optional[bool] = Field(None, description="Whether the aspect is required.")


class ItemAspectsRequest(EbayBaseModel):
    """Model for item aspects request parameters."""
    
    category_id: str = Field(..., description="The eBay category ID to get aspects for.")


class ItemAspectsResponse(EbayResponse[List[Aspect]]):
    """Response model for item aspects."""
    pass
