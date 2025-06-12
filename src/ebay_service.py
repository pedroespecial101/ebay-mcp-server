import os
import logging
import logging.handlers 
from typing import Optional, Union, Dict, Any
from dotenv import load_dotenv
import httpx
from ebay_mcp.auth.ebay_oauth import get_access_token

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

# Load environment variables from .env file in the project root
dotenv_path = os.path.join(project_root, '.env')
logger.info(f"Attempting to load .env from: {dotenv_path}")
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
    logger.info(".env file loaded successfully.")
else:
    logger.warning(f".env file not found at {dotenv_path}. Environment variables might not be set.")


async def get_ebay_access_token() -> str:
    """Return a valid eBay user access token via FastMCP OAuth helper.

    The helper will automatically launch an interactive login the first time and
    transparently refresh tokens thereafter.  Any failure is returned as an
    error string so existing callers continue to work.
    """
    logger.info("Fetching EBAY_USER_ACCESS_TOKEN using FastMCP OAuth helper …")

    try:
        token = await get_access_token()
        logger.debug(f"Retrieved token (first 10 chars): {token[:10]}…")
        return token
    except Exception as e:
        error_msg = (
            "Failed to retrieve eBay access token via OAuth helper. "
            "User likely needs to run the 'trigger_ebay_login' tool. "
            f"Details: {e}"
        )
        logger.error(error_msg)
        return error_msg


async def get_auth_config() -> EbayAuthConfig:
    """
    Get the eBay authentication configuration from the environment.
    
    Returns:
        EbayAuthConfig: The eBay authentication configuration.
    """
    # Still return static env-based config for now (may remove later)
    return EbayAuthConfig.from_env(dotenv_path)


async def get_server_config() -> ServerConfig:
    """
    Get the server configuration from the environment.
    
    Returns:
        ServerConfig: The server configuration.
    """
    return ServerConfig.from_env()
