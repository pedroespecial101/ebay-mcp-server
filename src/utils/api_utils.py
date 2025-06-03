"""
Shared API utilities for eBay API calls
"""
import logging
import asyncio
import httpx
import os
import sys
import json
from dotenv import load_dotenv

# Add the project root directory to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

# Import authentication functions
from ebay_auth.ebay_auth import refresh_access_token as ebay_auth_refresh_token
from ebay_service import get_ebay_access_token

# Load environment variables
load_dotenv()

# Get logger
logger = logging.getLogger(__name__)

# Determine if we're in DEBUG mode
DEBUG_MODE = os.getenv('MCP_LOG_LEVEL', 'NORMAL').upper() == 'DEBUG'

# Helper to check if token is an error message from our get_ebay_access_token function
def is_token_error(token: str) -> bool:
    """Checks if the token string is actually an error message from get_ebay_access_token."""
    if not token: # Handles empty string or None
        logger.warning("is_token_error received an empty or None token.")
        return True # Treat as error
    # Common prefixes for error messages returned by get_ebay_access_token
    error_prefixes = [
        "Failed to get access token", 
        "EBAY_CLIENT_ID or EBAY_CLIENT_SECRET is not set",
        "No access_token found in eBay response",
        "HTTPX RequestError occurred",
        "An unexpected error occurred",
        "EBAY_USER_ACCESS_TOKEN not found" # Added from ebay_service update
    ]
    return any(token.startswith(prefix) for prefix in error_prefixes)

def log_request_response_debug(request=None, response=None, error=None, prefix=''):
    """Log detailed request and response information when in DEBUG mode"""
    if not DEBUG_MODE:
        return
        
    if request:
        try:
            request_info = {
                'method': request.method,
                'url': str(request.url),
                'headers': dict(request.headers),
                'content': request.content.decode('utf-8') if request.content else None
            }
            logger.debug(f"{prefix} Request: {json.dumps(request_info, indent=2)}")
        except Exception as e:
            logger.debug(f"{prefix} Failed to log request details: {e}")
    
    if response:
        try:
            response_info = {
                'status_code': response.status_code,
                'headers': dict(response.headers),
                'content': response.text if hasattr(response, 'text') else None
            }
            logger.debug(f"{prefix} Response: {json.dumps(response_info, indent=2)}")
        except Exception as e:
            logger.debug(f"{prefix} Failed to log response details: {e}")
    
    if error:
        logger.debug(f"{prefix} Error: {error}")

async def execute_ebay_api_call(tool_name: str, client: httpx.AsyncClient, api_call_logic: callable):
    """
    Executes an eBay API call with token acquisition, 401 error handling, token refresh, and retry.

    Args:
        tool_name: Name of the MCP tool making the call (for logging).
        client: The httpx.AsyncClient instance.
        api_call_logic: An async callable that takes an access_token and the client,
                        and performs the actual API request. It should return the response text
                        or raise httpx.HTTPStatusError on API errors.
    Returns:
        The API response text on success, or an error message string on failure.
    """
    access_token = await get_ebay_access_token()
    if is_token_error(access_token):
        logger.error(f"{tool_name}: Initial token acquisition failed: {access_token}")
        return f"Token acquisition failed. Details: {access_token}"

    try:
        logger.info(f"{tool_name}: Attempting API call with current token: {access_token[:10]}...")
        if DEBUG_MODE:
            logger.debug(f"{tool_name}: Executing API call with full token: {access_token}")
        
        # Wrap the api_call_logic to intercept and log requests/responses
        async def wrapped_api_call(token, client):
            response_text = None
            response_obj = None
            request_obj = None
            
            try:
                # Call the original API logic and capture the response
                response_text = await api_call_logic(token, client)
                
                # If we're in DEBUG mode and the response isn't an error message,
                # log the request and response details (this can be extended based on the actual implementation)
                if DEBUG_MODE and hasattr(client, '_last_request') and hasattr(client, '_last_response'):
                    request_obj = getattr(client, '_last_request', None)
                    response_obj = getattr(client, '_last_response', None)
                    log_request_response_debug(request_obj, response_obj, prefix=f"{tool_name}")
                
                return response_text
            except Exception as e:
                if DEBUG_MODE:
                    logger.debug(f"{tool_name}: Exception in API call: {e}")
                    if hasattr(e, 'request'):
                        log_request_response_debug(request=e.request, prefix=f"{tool_name}")
                    if hasattr(e, 'response'):
                        log_request_response_debug(response=e.response, prefix=f"{tool_name}")
                raise
                
        return await wrapped_api_call(access_token, client)
    except httpx.HTTPStatusError as e:
        if DEBUG_MODE:
            log_request_response_debug(request=e.request, response=e.response, 
                                      error=f"HTTP Status Error: {e}", prefix=f"{tool_name}")
        if e.response.status_code == 401:
            logger.warning(f"{tool_name}: API call failed with 401 (Unauthorized). Token {access_token[:10]}... may be expired. Attempting refresh.")
            
            loop = asyncio.get_event_loop()
            new_token_value_after_refresh = await loop.run_in_executor(None, ebay_auth_refresh_token)

            if new_token_value_after_refresh:
                logger.info(f"{tool_name}: Token refresh process completed. New token value: {new_token_value_after_refresh[:10]}... Attempting to retrieve and retry API call.")
                refreshed_access_token = await get_ebay_access_token() # This should now pick up the new token from .env
                
                if is_token_error(refreshed_access_token):
                    error_msg = (f"{tool_name}: Failed to retrieve token from .env after refresh attempt. "
                                 f"The user needs to authenticate with eBay again. You can use the 'trigger_ebay_login' tool to help the user login. "
                                 f"This will open a browser window for eBay login. Once completed, try this request again!")
                    logger.error(error_msg)
                    return error_msg
                
                logger.info(f"{tool_name}: Retrying API call with refreshed token: {refreshed_access_token[:10]}...")
                try:
                    return await api_call_logic(refreshed_access_token, client)
                except httpx.HTTPStatusError as retry_e:
                    error_msg = f"{tool_name}: API call failed again after token refresh with status {retry_e.response.status_code}: {retry_e.response.text}"
                    logger.error(error_msg)
                    return error_msg
                except Exception as retry_e_general:
                    error_msg = f"{tool_name}: Unexpected error during API call retry after token refresh: {retry_e_general}"
                    logger.exception(error_msg)
                    return error_msg
            else:
                error_msg = (f"{tool_name}: Token refresh attempt failed. The user's eBay authentication has expired and needs to be renewed. "
                             f"You can use the 'trigger_ebay_login' tool to help the user login to eBay again. "
                             f"This will open a browser window for eBay authentication. Once the user completes this process, try this request again!")
                logger.error(error_msg)
                return error_msg
        else:
            error_msg = f"{tool_name}: eBay API request failed with status code {e.response.status_code}: {e.response.text}"
            logger.error(error_msg)
            return error_msg
    except httpx.RequestError as e:
        error_msg = f"{tool_name}: HTTPX RequestError occurred during eBay API request: {e}"
        logger.exception(error_msg)
        return error_msg
    except Exception as e:
        error_msg = f"{tool_name}: An unexpected error occurred during eBay API request: {e}"
        logger.exception(error_msg)
        return error_msg
