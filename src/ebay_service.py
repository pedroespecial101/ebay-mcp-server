import os
import logging
import logging.handlers 
from dotenv import load_dotenv
import httpx
from ebay_auth.ebay_auth import get_env_variable as get_ebay_auth_env_variable

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
# Ensure logs from this module will be output if the root logger is configured for INFO
# If the MCP server or another part of the application configures logging, this might be overridden.
# BasicConfig is a no-op if handlers are already configured for the root logger.

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
    """
    logger.info("Attempting to retrieve EBAY_USER_ACCESS_TOKEN from .env via ebay_auth module.")
    
    # The ebay_auth module's get_env_variable handles its own .env loading and path finding.
    access_token = get_ebay_auth_env_variable("EBAY_USER_ACCESS_TOKEN")

    if access_token:
        logger.info("Successfully retrieved EBAY_USER_ACCESS_TOKEN.")
        logger.debug(f"get_ebay_access_token: EBAY_USER_ACCESS_TOKEN (first 10 chars): {access_token[:10]}...")
        return access_token
    else:
        error_msg = ("EBAY_USER_ACCESS_TOKEN not found. "
                     "Please use the 'trigger_ebay_login' MCP tool to authenticate with eBay. "
                     "After successful login and restarting the MCP server, this token should be available.")
        logger.error(error_msg)
        return error_msg
