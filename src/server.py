from fastmcp import FastMCP
import httpx
import os
import sys
import logging
import logging.handlers

# Add the src directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --- Centralized Logging Configuration --- 
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
LOG_FILE_PATH = os.path.join(LOG_DIR, 'fastmcp_server.log')

# Ensure log directory exists
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# Get the root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG) # Set root logger level (can be overridden by handlers)

# Formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Timed Rotating File Handler
# Rotates at midnight, keeps 7 backups
timed_handler = logging.handlers.TimedRotatingFileHandler(
    LOG_FILE_PATH, 
    when='midnight', 
    interval=1, 
    backupCount=7
)
timed_handler.setFormatter(formatter)
timed_handler.setLevel(logging.DEBUG) # Set handler level, e.g., DEBUG or INFO

# Add handler to the root logger
root_logger.addHandler(timed_handler)

# Console Handler (optional, for seeing logs in console if not using nohup or for direct runs)
# console_handler = logging.StreamHandler()
# console_handler.setFormatter(formatter)
# console_handler.setLevel(logging.INFO) # Or DEBUG
# root_logger.addHandler(console_handler)

logger = logging.getLogger(__name__) # Get a logger for this specific module (server.py)
logger.info("Logging configured with TimedRotatingFileHandler.")
# --- End of Centralized Logging Configuration ---


# Import the token function from ebay_service (logger from ebay_service is no longer needed here for config)
import asyncio # New import
from ebay_auth.ebay_auth import refresh_access_token as ebay_auth_refresh_token # New import
from src.ebay_service import get_ebay_access_token # Original import

# Create an MCP server
mcp = FastMCP("Ebay API")

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

async def _execute_ebay_api_call(tool_name: str, client: httpx.AsyncClient, api_call_logic: callable):
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
        return await api_call_logic(access_token, client)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            logger.warning(f"{tool_name}: API call failed with 401 (Unauthorized). Token {access_token[:10]}... may be expired. Attempting refresh.")
            
            loop = asyncio.get_event_loop()
            new_token_value_after_refresh = await loop.run_in_executor(None, ebay_auth_refresh_token)

            if new_token_value_after_refresh:
                logger.info(f"{tool_name}: Token refresh process completed. New token value: {new_token_value_after_refresh[:10]}... Attempting to retrieve and retry API call.")
                refreshed_access_token = await get_ebay_access_token() # This should now pick up the new token from .env
                
                if is_token_error(refreshed_access_token):
                    error_msg = f"{tool_name}: Failed to retrieve token from .env after refresh attempt: {refreshed_access_token}"
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
                error_msg = f"{tool_name}: Token refresh attempt failed (ebay_auth_refresh_token returned None). Original 401 error for token {access_token[:10]}...: {e.response.text}"
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

# Add an addition tool
@mcp.tool()
async def test_auth() -> str:
    """Test authentication and token retrieval"""
    logger.info("Executing test_auth MCP tool.")
    token = await get_ebay_access_token()
    
    if is_token_error(token):
        logger.error(f"test_auth: Token acquisition failed: {token}")
        # Return the specific error message from get_ebay_access_token
        return f"Token acquisition failed. Details: {token}"
    
    logger.info(f"test_auth: Token successfully retrieved. Length: {len(token)}")
    # Return first 50 chars of token and the length
    return f"Token found (first 50 chars): {token[:50]}...\nToken length: {len(token)}"

@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""
    logger.debug(f"Executing add MCP tool with a={a}, b={b}")
    return a + b


# Add a tool to search eBay items using Browse API
@mcp.tool()
async def search_ebay_items(query: str, limit: int = 10) -> str:
    """Search items on eBay using Browse API"""
    logger.info(f"Executing search_ebay_items MCP tool with query='{query}', limit={limit}.")

    async def _api_call(access_token: str, client: httpx.AsyncClient):
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        params = {"q": query, "limit": limit}
        url = "https://api.ebay.com/buy/browse/v1/item_summary/search"
        logger.debug(f"search_ebay_items: Requesting URL: {url} with params: {params} using token {access_token[:10]}...")
        
        response = await client.get(url, headers=headers, params=params)
        logger.debug(f"search_ebay_items: Response status: {response.status_code}")
        response.raise_for_status() # Crucial for _execute_ebay_api_call to handle HTTP errors
        logger.info("search_ebay_items: Successfully fetched items.")
        return response.text

    async with httpx.AsyncClient() as client:
        return await _execute_ebay_api_call("search_ebay_items", client, _api_call)

@mcp.tool()
async def get_category_suggestions(query: str) -> str:
    """Get category suggestions from eBay Taxonomy API for the UK catalogue."""
    logger.info(f"Executing get_category_suggestions MCP tool with query='{query}'.")

    async def _api_call(access_token: str, client: httpx.AsyncClient):
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        params = {"q": query}
        url = "https://api.ebay.com/commerce/taxonomy/v1/category_tree/3/get_category_suggestions"
        logger.debug(f"get_category_suggestions: Requesting URL: {url} with params: {params} using token {access_token[:10]}...")
        
        response = await client.get(url, headers=headers, params=params)
        logger.debug(f"get_category_suggestions: Response status: {response.status_code}")
        response.raise_for_status()
        logger.info("get_category_suggestions: Successfully fetched category suggestions.")
        return response.text

    async with httpx.AsyncClient() as client:
        return await _execute_ebay_api_call("get_category_suggestions", client, _api_call)

@mcp.tool()
async def get_item_aspects_for_category(category_id: str) -> str:
    """Get item aspects for a specific category from eBay Taxonomy API.
    
    Args:
        category_id: The eBay category ID to get aspects for.
    """
    logger.info(f"Executing get_item_aspects_for_category MCP tool with category_id='{category_id}'.")

    async def _api_call(access_token: str, client: httpx.AsyncClient):
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        url = f"https://api.ebay.com/commerce/taxonomy/v1/category_tree/3/get_item_aspects_for_category"
        logger.debug(f"get_item_aspects_for_category: Requesting URL: {url} with category_id: {category_id} using token {access_token[:10]}...")
        
        response = await client.get(url, headers=headers, params={"category_id": category_id})
        logger.debug(f"get_item_aspects_for_category: Response status: {response.status_code}")
        response.raise_for_status()
        logger.info("get_item_aspects_for_category: Successfully fetched item aspects.")
        return response.text

    async with httpx.AsyncClient() as client:
        return await _execute_ebay_api_call("get_item_aspects_for_category", client, _api_call)

@mcp.tool()
async def get_offer_by_sku(sku: str) -> str:
    """Get offer details for a specific SKU from eBay Sell Inventory API.
    
    Args:
        sku: The seller-defined SKU (Stock Keeping Unit) of the offer.
    """
    logger.info(f"Executing get_offer_by_sku MCP tool with SKU='{sku}'.")

    async def _api_call(access_token: str, client: httpx.AsyncClient):
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-EBAY-C-MARKETPLACE-ID": "EBAY_GB",
            "Accept-Language": "en-GB",
        }
        base_url = "https://api.ebay.com/sell/inventory/v1/offer"
        
        log_headers = headers.copy()
        log_headers['Authorization'] = f"Bearer {access_token[:20]}...<truncated>"
        logger.debug(f"get_offer_by_sku: Headers for API call: {log_headers}")
        logger.debug(f"get_offer_by_sku: Request URL for direct SKU lookup: {base_url}?sku={sku} using token {access_token[:10]}...")

        # Initial attempt: Direct SKU lookup
        response = await client.get(base_url, headers=headers, params={"sku": sku})
        logger.info(f"get_offer_by_sku: Direct SKU lookup response status: {response.status_code}")
        response_text_snippet = response.text[:500] if response.text else "[Empty Response Body]"
        logger.debug(f"get_offer_by_sku: Direct SKU lookup response text (first 500 chars): {response_text_snippet}...")

        # If direct lookup fails with 403/404 (or other client error that's not 401, which is handled by _execute_ebay_api_call),
        # try the alternative approach of listing offers.
        # Note: response.raise_for_status() will be called *after* this block if status is still not 200.
        if response.status_code in [403, 404]: 
            logger.warning(f"get_offer_by_sku: Direct SKU lookup failed with {response.status_code}. Trying alternative approach (listing offers).")
            
            list_offers_params = {"sku": sku, "limit": 1}
            logger.debug(f"get_offer_by_sku: Listing offers with params: {list_offers_params}")
            offers_response = await client.get(base_url, headers=headers, params=list_offers_params)
            
            logger.info(f"get_offer_by_sku: Offer list response status: {offers_response.status_code}")
            offers_response_text_snippet = offers_response.text[:500] if offers_response.text else "[Empty Response Body]"
            logger.debug(f"get_offer_by_sku: Offer list response text (first 500 chars): {offers_response_text_snippet}...")
            
            if offers_response.status_code == 200:
                offers_data = offers_response.json()
                if offers_data.get('offers') and len(offers_data['offers']) > 0:
                    offer_id = offers_data['offers'][0].get('offerId')
                    if offer_id:
                        logger.info(f"get_offer_by_sku: Found offer ID: {offer_id} from listing. Fetching details.")
                        offer_detail_url = f"{base_url}/{offer_id}"
                        response = await client.get(offer_detail_url, headers=headers) # Re-assign response
                        logger.info(f"get_offer_by_sku: Offer details response status (after listing): {response.status_code}")
                        response_text_snippet_detail = response.text[:500] if response.text else "[Empty Response Body]"
                        logger.debug(f"get_offer_by_sku: Offer details response text (first 500 chars): {response_text_snippet_detail}...")
                    else:
                        logger.warning("get_offer_by_sku: 'offerId' not found in listed offer. Original direct lookup response will be used.")
                else:
                    logger.warning(f"get_offer_by_sku: No offers found in the listing for SKU {sku}. Original direct lookup response will be used.")
            else:
                logger.error(f"get_offer_by_sku: Failed to list offers (alternative approach), status: {offers_response.status_code}. Original direct lookup response will be used.")
        
        # After potential fallback, raise for status on the final 'response' object.
        # This allows _execute_ebay_api_call to handle 401s from either direct or fallback calls.
        response.raise_for_status()
        
        logger.info(f"get_offer_by_sku: Successfully fetched offer for SKU {sku}.")
        return response.text

    async with httpx.AsyncClient() as client:
        return await _execute_ebay_api_call("get_offer_by_sku", client, _api_call)


if __name__ == "__main__":
    logger.info("Starting FastMCP server with stdio transport...")
    logger.info("To test authentication, use the MCP client to call the 'test_auth' function or other tools.")
    logger.info(f"Logging to: {LOG_FILE_PATH}")
    logger.info("Attempting to call mcp.run()...")
    mcp.run(transport="stdio")
    logger.info("mcp.run() completed or exited.")
