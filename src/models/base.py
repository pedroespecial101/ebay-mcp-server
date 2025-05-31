"""
Base models for eBay MCP Server.
Contains base classes and shared functionality for all models.
"""
from typing import Any, Dict, List, Optional, Type, Union, TypeVar, Generic
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar('T')

class EbayBaseModel(BaseModel):
    """Base model for all eBay MCP Server models."""
    
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={"examples": []},
        strict=False,
        arbitrary_types_allowed=True,
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return self.model_dump()
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EbayBaseModel':
        """Create model from dictionary."""
        return cls(**data)


class EbayResponse(EbayBaseModel, Generic[T]):
    """Base model for eBay API responses."""
    
    success: bool = Field(
        True, 
        description="Whether the API call was successful."
    )
    error_message: Optional[str] = Field(
        None, 
        description="Error message if the API call failed."
    )
    data: Optional[T] = Field(
        None, 
        description="Response data."
    )
    
    @classmethod
    def success_response(cls, data: T) -> 'EbayResponse[T]':
        """Create a successful response."""
        return cls(success=True, data=data)
    
    @classmethod
    def error_response(cls, error_message: str) -> 'EbayResponse[T]':
        """Create an error response."""
        return cls(success=False, error_message=error_message, data=None)
