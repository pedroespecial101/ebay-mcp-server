"""
Configuration models for eBay MCP Server.
These models handle environment variables and server settings.
"""
import os
from pathlib import Path

from dotenv import dotenv_values
from pydantic import BaseModel, Field


AUTH_ENV_KEYS = (
    "EBAY_CLIENT_ID",
    "EBAY_CLIENT_SECRET",
    "EBAY_RU_NAME",
    "EBAY_APP_CONFIGURED_REDIRECT_URI",
    "EBAY_USER_ACCESS_TOKEN",
    "EBAY_USER_REFRESH_TOKEN",
    "EBAY_USER_ID",
    "EBAY_USER_NAME",
)


def _read_credentials_file(credentials_source: str | None) -> dict[str, str | None]:
    if not credentials_source:
        return {}

    path = Path(credentials_source).expanduser()
    if not path.is_file():
        return {}

    parsed = dotenv_values(path)
    return {key: parsed.get(key) for key in AUTH_ENV_KEYS}


def _value(key: str, file_values: dict[str, str | None], default: str | None = None) -> str | None:
    return os.getenv(key, file_values.get(key, default))

class EbayAuthConfig(BaseModel):
    """eBay authentication configuration."""
    
    client_id: str = Field(..., description="eBay Application Client ID")
    client_secret: str = Field(..., description="eBay Application Client Secret")
    ru_name: str = Field(..., description="eBay RuName (Redirect URL Name)")
    redirect_uri: str = Field(..., description="eBay Application Configured Redirect URI")
    
    # User authentication tokens
    user_access_token: str | None = Field(None, description="eBay User Access Token")
    user_refresh_token: str | None = Field(None, description="eBay User Refresh Token")
    user_id: str | None = Field(None, description="eBay User ID")
    user_name: str | None = Field(None, description="eBay User Name")
    
    @classmethod
    def from_env(cls, dotenv_path: str | None = None) -> 'EbayAuthConfig':
        """Load configuration from environment variables."""
        credentials_source = dotenv_path or os.getenv("EBAY_CREDENTIALS_FILE")
        file_values = _read_credentials_file(credentials_source)

        return cls(
            client_id=_value("EBAY_CLIENT_ID", file_values, "") or "",
            client_secret=_value("EBAY_CLIENT_SECRET", file_values, "") or "",
            ru_name=_value("EBAY_RU_NAME", file_values, "") or "",
            redirect_uri=_value("EBAY_APP_CONFIGURED_REDIRECT_URI", file_values, "") or "",
            user_access_token=_value("EBAY_USER_ACCESS_TOKEN", file_values),
            user_refresh_token=_value("EBAY_USER_REFRESH_TOKEN", file_values),
            user_id=_value("EBAY_USER_ID", file_values),
            user_name=_value("EBAY_USER_NAME", file_values),
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
