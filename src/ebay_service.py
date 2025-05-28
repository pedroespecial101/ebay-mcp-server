import os
import logging
import logging.handlers 
from dotenv import load_dotenv
import httpx

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
    """Get eBay API access token using either the provided OAuth token or client credentials."""
    
    use_env_oauth_token_str = os.getenv("USE_ENV_OAUTH_TOKEN", "False").lower()
    use_env_oauth_token = use_env_oauth_token_str == "true"
    
    logger.debug(f"USE_ENV_OAUTH_TOKEN flag is set to: {use_env_oauth_token}")

    if use_env_oauth_token:
        oauth_token = os.getenv("EBAY_OAUTH_TOKEN")
        if oauth_token:
            logger.info("Using EBAY_OAUTH_TOKEN from environment as per USE_ENV_OAUTH_TOKEN=True.")
            logger.debug(f"get_ebay_access_token: EBAY_OAUTH_TOKEN (first 10 chars): {oauth_token[:10]}...")
            return oauth_token
        else:
            logger.warning("USE_ENV_OAUTH_TOKEN is True, but EBAY_OAUTH_TOKEN is not set in environment. Falling back to client credentials.")
    else:
        logger.info("USE_ENV_OAUTH_TOKEN is False or not set. Attempting client credentials flow.")

    # Fallback to client credentials flow
    client_id = os.getenv("EBAY_CLIENT_ID")
    client_secret = os.getenv("EBAY_CLIENT_SECRET") 

    if not client_id or not client_secret:
        error_msg = "EBAY_CLIENT_ID or EBAY_CLIENT_SECRET is not set in environment variables for client credentials flow."
        logger.error(error_msg)
        return error_msg

    token_url = "https://api.ebay.com/identity/v1/oauth2/token"
    auth = httpx.BasicAuth(client_id, client_secret)
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
    }
    # Refined list of scopes
    scopes = [
        "https://api.ebay.com/oauth/api_scope",  # View public data from eBay
    #    "https://api.ebay.com/oauth/api_scope/sell.inventory",  # View and manage your inventory and offers
    #    "https://api.ebay.com/oauth/api_scope/sell.account.readonly",  # View your account settings
    #    "https://api.ebay.com/oauth/api_scope/sell.fulfillment.readonly",  # View your order fulfillments
    #    "https://api.ebay.com/oauth/api_scope/commerce.identity.readonly"  # View user's basic information
    ]
    
    data = {
        "grant_type": "client_credentials",
        "scope": " ".join(scopes),  
    }
    logger.debug(f"Requesting token with scopes: {data['scope']}")

    async with httpx.AsyncClient() as client:
        try:
            logger.info(f"Requesting access token from {token_url} using client credentials.")
            response = await client.post(
                token_url, headers=headers, data=data, auth=auth
            )
            response_data = response.json() 
            if response.status_code != 200:
                error_msg = f"Failed to get access token via client credentials: {response.status_code} - {response.text}"
                logger.error(error_msg)
                if "errors" in response_data:
                    for err in response_data["errors"]:
                        logger.error(f"eBay API Error: ID {err.get('errorId')}, Domain: {err.get('domain')}, Category: {err.get('category')}, Message: {err.get('message')}")
                return error_msg 
                
            access_token = response_data.get("access_token")
            if not access_token:
                error_msg = "No access_token found in eBay response though status was 200."
                logger.error(error_msg)
                return error_msg
                
            logger.info("Successfully obtained new access token via client credentials.")
            logger.debug(f"Obtained token (first 10 chars): {access_token[:10]}...")
            return access_token
        except httpx.RequestError as e:
            error_msg = f"HTTPX RequestError occurred when requesting access token: {e}"
            logger.exception(error_msg)
            return error_msg
        except Exception as e:
            error_msg = f"An unexpected error occurred when requesting access token: {e}"
            logger.exception(error_msg)
            return error_msg
