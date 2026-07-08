import os
import asyncio
import logging
import logging.handlers 
from typing import Optional, Union, Dict, Any
from dotenv import load_dotenv
import httpx
from ebay_auth.ebay_auth import refresh_access_token

# Import Pydantic models
from models.config.settings import EbayAuthConfig, ServerConfig
from models.auth import TokenResponse
from models.base import EbayResponse

# --- Logging Setup ---
# Get the absolute path to the directory where this script is located
script_dir = os.path.dirname(os.path.abspath(__file__))
# Construct the path to the project root
project_root = os.path.join(script_dir, '..')
logs_dir = os.path.join(project_root, 'logs')
os.makedirs(logs_dir, exist_ok=True) 

log_file_path = os.path.join(logs_dir, 'fastmcp_server.log')

# Configure logger for this module
logger = logging.getLogger(__name__)

# --- End Logging Setup ---

def _resolve_credentials_path() -> str | None:
    credentials_file = os.getenv("EBAY_CREDENTIALS_FILE")
    if credentials_file:
        return os.path.expanduser(credentials_file)
    if os.getenv("EBAY_TOKEN_STORE", "").lower() == "doppler":
        return None
    return os.path.join(project_root, '.env')


# Load environment variables from the configured credentials source when present.
dotenv_path = _resolve_credentials_path()
if dotenv_path and os.path.exists(dotenv_path):
    logger.info(f"Loading credentials from: {dotenv_path}")
    load_dotenv(dotenv_path)
    logger.info("Credentials file loaded successfully.")
elif dotenv_path:
    logger.warning(f"Credentials file not found at {dotenv_path}. Environment variables might not be set.")
else:
    logger.info("Using injected environment credentials without a local dotenv file.")


async def get_ebay_access_token() -> str:
    """
    Retrieve the current eBay user access token, refreshing it when necessary.
    
    Returns:
        str: The access token if available, otherwise an error message.
    """
    logger.info("Attempting to retrieve the eBay user access token.")
    auth_config = EbayAuthConfig.from_env(dotenv_path)

    if auth_config.user_access_token:
        logger.info("Successfully retrieved EBAY_USER_ACCESS_TOKEN.")
        return auth_config.user_access_token

    if auth_config.is_app_configured() and auth_config.user_refresh_token:
        logger.info("No access token is loaded; refreshing it from the stored refresh token.")
        refreshed_token = await asyncio.to_thread(
            refresh_access_token,
            auth_config.client_id,
            auth_config.client_secret,
            auth_config.user_refresh_token,
        )
        if refreshed_token:
            return refreshed_token

    error_msg = (
        "EBAY_USER_ACCESS_TOKEN not found and automatic refresh was unavailable. "
        "Run the trigger_ebay_login tool to authenticate the seller account."
    )
    logger.error(error_msg)
    return error_msg


async def get_auth_config() -> EbayAuthConfig:
    """
    Get the eBay authentication configuration from the environment.
    
    Returns:
        EbayAuthConfig: The eBay authentication configuration.
    """
    return EbayAuthConfig.from_env(dotenv_path)


async def get_server_config() -> ServerConfig:
    """
    Get the server configuration from the environment.
    
    Returns:
        ServerConfig: The server configuration.
    """
    return ServerConfig.from_env()
