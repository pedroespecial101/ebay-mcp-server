"""
Authentication models for eBay MCP Server.
"""
from typing import Optional, Dict, Any
from pydantic import Field
from .base import EbayBaseModel


class TokenResponse(EbayBaseModel):
    """eBay token response model."""
    
    access_token: str = Field(..., description="OAuth access token.")
    token_type: str = Field(..., description="Token type, typically 'Bearer'.")
    expires_in: int = Field(..., description="Token lifetime in seconds.")
    refresh_token: Optional[str] = Field(None, description="OAuth refresh token.")
    

class UserDetails(EbayBaseModel):
    """eBay user details model."""
    
    user_id: str = Field(..., description="eBay user ID.")
    username: str = Field(..., description="eBay username.")
    
    
class LoginResult(EbayBaseModel):
    """Result of the login process."""
    
    status: str = Field(..., description="Status of the login process.")
    message: str = Field(..., description="Message describing the login result.")
    user_name: Optional[str] = Field(None, description="eBay username if login was successful.")
    error: Optional[str] = Field(None, description="Error message if login failed.")
    error_details: Optional[str] = Field(None, description="Detailed error information.")
    

class AuthCodeResponse(EbayBaseModel):
    """OAuth authorization code response model."""
    
    auth_code: Optional[str] = Field(None, description="OAuth authorization code.")
    error: Optional[Dict[str, Any]] = Field(None, description="Error details if authorization failed.")
    state: Optional[str] = Field(None, description="State parameter for CSRF protection.")
