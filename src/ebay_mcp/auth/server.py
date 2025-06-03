"""
eBay Auth MCP Server - Handles eBay Authentication APIs
"""
import logging
import os
import sys
import asyncio
from fastmcp import FastMCP
import json

# Add the project root directory to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(project_root)

# Import auth-related models and functions
from models.auth import LoginResult
from models.mcp_tools import TestAuthResponse, TriggerEbayLoginResponse
from ebay_auth.ebay_auth import refresh_access_token as ebay_auth_refresh_token
from ebay_auth.ebay_auth import initiate_user_login
from ebay_service import get_ebay_access_token
from utils.api_utils import execute_ebay_api_call, is_token_error

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
        token = await get_ebay_access_token()
        
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
        loop = asyncio.get_event_loop()
        # Run the synchronous initiate_user_login in a separate thread
        # initiate_user_login handles its own browser opening and local server for callback
        login_result = await loop.run_in_executor(None, initiate_user_login)
        
        if login_result and login_result.get("status") == "success":
            logger.info("trigger_ebay_login: eBay login process completed successfully according to initiate_user_login.")
            # Get the user details if available
            user_name = login_result.get("user_name", "TreadersLoft")
            # Create and return a success response using the Pydantic model
            response = TriggerEbayLoginResponse.success_response(user_name)
            return response.data
        elif login_result and "error" in login_result:
            error_message = login_result.get("message", "Unknown error")
            error_details = login_result.get("error_details", "No specific error details provided.")
            logger.error(f"trigger_ebay_login: eBay login process failed. Error: {error_message}, Details: {error_details}")
            # Create and return an error response using the Pydantic model
            response = TriggerEbayLoginResponse.error_response(error_message, error_details)
            return response.data
        else:
            # This case might occur if initiate_user_login returns None or an unexpected structure
            logger.warning(f"trigger_ebay_login: eBay login process finished, but the result was unexpected: {login_result}")
            # Create and return an uncertain response using the Pydantic model
            response = TriggerEbayLoginResponse.uncertain_response(login_result)
            return response.data

    except Exception as e:
        logger.exception("trigger_ebay_login: An unexpected error occurred while trying to initiate eBay login.")
        # Create and return an error response for the exception
        response = TriggerEbayLoginResponse.error_response(
            "An unexpected error occurred while trying to initiate eBay login", 
            str(e)
        )
        return response.data
