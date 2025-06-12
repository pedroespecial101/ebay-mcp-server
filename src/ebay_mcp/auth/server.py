"""
eBay Auth MCP Server - Handles eBay Authentication APIs
"""
import logging
import os
import sys
import asyncio
from fastmcp import FastMCP
import json
import httpx
from dotenv import load_dotenv

# Add the project root directory to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(project_root)

# Import auth-related models and functions
from models.auth import LoginResult
from models.mcp_tools import TestAuthResponse, TriggerEbayLoginResponse
from ebay_mcp.auth.ebay_oauth import get_ebay_oauth, get_access_token
from ebay_auth.ebay_auth import get_user_details
from utils.api_utils import is_token_error

# Load environment variables
load_dotenv()

# Determine if we're in DEBUG mode
DEBUG_MODE = os.getenv('MCP_LOG_LEVEL', 'NORMAL').upper() == 'DEBUG'

# Get logger
logger = logging.getLogger(__name__)

# Create Auth MCP server
auth_mcp = FastMCP("eBay Auth API")

# Helper to check if token is an error message
def is_token_error(token: str) -> bool:
    """Checks if the token string is actually an error message from get_ebay_access_token."""
    if not token:  # Handles empty string or None
        logger.warning("is_token_error received an empty or None token.")
        return True  # Treat as error
    # Common prefixes for error messages returned by get_ebay_access_token
    error_prefixes = [
        "Failed to get access token", 
        "EBAY_CLIENT_ID or EBAY_CLIENT_SECRET is not set",
        "No access_token found in eBay response",
        "HTTPX RequestError occurred",
        "An unexpected error occurred",
        "EBAY_USER_ACCESS_TOKEN not found"  # Added from ebay_service update
    ]
    return any(token.startswith(prefix) for prefix in error_prefixes)

@auth_mcp.tool()
async def test_auth() -> str:
    """Test authentication and token retrieval"""
    logger.info("Executing test_auth MCP tool.")
    
    try:
        token = await get_access_token()
        
        if is_token_error(token):
            logger.error(f"test_auth: Token acquisition failed: {token}")
            # Create and return an error response using the Pydantic model
            response = TestAuthResponse.error_response(token)
            return response.data
        
        logger.info(f"test_auth: Token successfully retrieved. Length: {len(token)}")
        # Create and return a success response using the Pydantic model
        response = TestAuthResponse.success_response(token)
        return response.data
    except Exception as e:
        logger.exception(f"test_auth: Unexpected error during token retrieval: {str(e)}")
        # Handle unexpected errors
        response = TestAuthResponse.error_response(f"Unexpected error during token retrieval: {str(e)}")
        return response.data

@auth_mcp.tool()
async def trigger_ebay_login() -> str:
    """Initiates the eBay OAuth2 login flow. 
    
    This will open a browser window for eBay authentication. After successful login, 
    the .env file will be updated with new tokens.
    IMPORTANT: You MUST restart the MCP server in your IDE after completing the login 
    for the new tokens to take effect.
    """
    logger.info("Executing trigger_ebay_login MCP tool.")
    try:
        oauth = get_ebay_oauth()
        # Open browser if necessary
        await oauth.login()

        token = await oauth.get_token()
        # Optionally get user details via existing util
        user_id, user_name = get_user_details(access_token=token)

        response = TriggerEbayLoginResponse.success_response(user_name or "eBay User")
        return response.data

    except Exception as e:
        logger.exception("trigger_ebay_login: OAuth login failed.")
        response = TriggerEbayLoginResponse.error_response("OAuth login failed", str(e))
        return response.data
