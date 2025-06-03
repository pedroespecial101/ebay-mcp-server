"""
Configuration models for eBay MCP Server.
These models handle environment variables and server settings.
"""
from typing import Optional, List
from pydantic import BaseModel, Field, validator
import os
from dotenv import load_dotenv

class EbayAuthConfig(BaseModel):
    """eBay authentication configuration."""
    
    client_id: str = Field(..., description="eBay Application Client ID")
    client_secret: str = Field(..., description="eBay Application Client Secret")
    ru_name: str = Field(..., description="eBay RuName (Redirect URL Name)")
    redirect_uri: str = Field(..., description="eBay Application Configured Redirect URI")
    
    # User authentication tokens
    user_access_token: Optional[str] = Field(None, description="eBay User Access Token")
    user_refresh_token: Optional[str] = Field(None, description="eBay User Refresh Token")
    user_id: Optional[str] = Field(None, description="eBay User ID")
    user_name: Optional[str] = Field(None, description="eBay User Name")
    
    @classmethod
    def from_env(cls, dotenv_path: Optional[str] = None) -> 'EbayAuthConfig':
        """Load configuration from environment variables."""
        if dotenv_path and os.path.exists(dotenv_path):
            load_dotenv(dotenv_path)
        
        return cls(
            client_id=os.getenv("EBAY_CLIENT_ID", ""),
            client_secret=os.getenv("EBAY_CLIENT_SECRET", ""),
            ru_name=os.getenv("EBAY_RU_NAME", ""),
            redirect_uri=os.getenv("EBAY_APP_CONFIGURED_REDIRECT_URI", ""),
            user_access_token=os.getenv("EBAY_USER_ACCESS_TOKEN"),
            user_refresh_token=os.getenv("EBAY_USER_REFRESH_TOKEN"),
            user_id=os.getenv("EBAY_USER_ID"),
            user_name=os.getenv("EBAY_USER_NAME")
        )
    
    def is_app_configured(self) -> bool:
        """Check if application credentials are configured."""
        return bool(self.client_id and self.client_secret and self.ru_name and self.redirect_uri)
    
    def is_user_authenticated(self) -> bool:
        """Check if user authentication tokens are available."""
        return bool(self.user_access_token and self.user_refresh_token)


class ServerConfig(BaseModel):
    """Server configuration settings."""
    
    log_level: str = Field("INFO", description="Logging level")
    log_dir: str = Field("logs", description="Directory for log files")
    log_file: str = Field("fastmcp_server.log", description="Log file name")
    
    @classmethod
    def from_env(cls) -> 'ServerConfig':
        """Load configuration from environment variables."""
        return cls(
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            log_dir=os.getenv("LOG_DIR", "logs"),
            log_file=os.getenv("LOG_FILE", "fastmcp_server.log")
        )
