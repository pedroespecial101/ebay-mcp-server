import os
import logging
import logging.handlers 
from typing import Optional, Union, Dict, Any
from dotenv import load_dotenv
import httpx
from ebay_auth.ebay_auth import get_env_variable as get_ebay_auth_env_variable

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
    """
    Retrieves the current eBay User Access Token from the .env file.
    This token is expected to be managed (e.g., refreshed) by the ebay_auth module.
    
    Returns:
        str: The access token if available, otherwise an error message.
    """
    logger.info("Attempting to retrieve EBAY_USER_ACCESS_TOKEN from .env via ebay_auth module.")
    
    # Get the auth configuration from environment variables
    auth_config = EbayAuthConfig.from_env(dotenv_path)
    
    if auth_config.user_access_token:
        logger.info("Successfully retrieved EBAY_USER_ACCESS_TOKEN.")
        logger.debug(f"get_ebay_access_token: EBAY_USER_ACCESS_TOKEN (first 10 chars): {auth_config.user_access_token[:10]}...")
        return auth_config.user_access_token
    else:
        error_msg = ("The user's EBAY_USER_ACCESS_TOKEN was not found. The user needs to authenticate with eBay before they can use this MCP. "
                     "You can use the 'trigger_ebay_login' tool. This will open a browser window for eBay login by the user. "
                     "Once they have completed this process, you should be able to try your request again!")
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
