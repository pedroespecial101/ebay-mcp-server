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
from src.ebay_service import get_ebay_access_token # Removed logger import from here

# Create an MCP server
mcp = FastMCP("Ebay API")

# Helper to check if token is an error message from our get_ebay_access_token function
def is_token_error(token: str) -> bool:
    """Checks if the token string is actually an error message from get_ebay_access_token."""
    if not token: # Handles empty string or None, which shouldn't happen with current get_ebay_access_token
        logger.warning("is_token_error received an empty or None token.")
        return True # Treat as error
    # Common prefixes for error messages returned by get_ebay_access_token
    error_prefixes = [
        "Failed to get access token", 
        "EBAY_CLIENT_ID or EBAY_CLIENT_SECRET is not set",
        "No access_token found in eBay response",
        "HTTPX RequestError occurred",
        "An unexpected error occurred"
    ]
    return any(token.startswith(prefix) for prefix in error_prefixes)

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
    async with httpx.AsyncClient() as client:
        token = await get_ebay_access_token()
        if is_token_error(token):
            logger.error(f"search_ebay_items: Token acquisition failed: {token}")
            return f"Token acquisition failed. Details: {token}"

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        params = {"q": query, "limit": limit}
        url = "https://api.ebay.com/buy/browse/v1/item_summary/search"
        logger.debug(f"search_ebay_items: Requesting URL: {url} with params: {params}")
        logger.debug(f"search_ebay_items: Headers: {{'Authorization': 'Bearer {token[:20]}...', ...}}") # Log partial token
        try:
            response = await client.get(url, headers=headers, params=params)
            logger.debug(f"search_ebay_items: Response status: {response.status_code}")
            if response.status_code != 200:
                error_msg = f"eBay API request (search_ebay_items) failed with status code {response.status_code}: {response.text}"
                logger.error(error_msg)
                return error_msg
            logger.info("search_ebay_items: Successfully fetched items.")
            return response.text
        except Exception as e:
            error_msg = f"Error occurred during search_ebay_items eBay API request: {e}"
            logger.exception(error_msg) # Logs full traceback
            return error_msg

@mcp.tool()
async def get_category_suggestions(query: str) -> str:
    """Get category suggestions from eBay Taxonomy API for the UK catalogue."""
    logger.info(f"Executing get_category_suggestions MCP tool with query='{query}'.")
    async with httpx.AsyncClient() as client:
        token = await get_ebay_access_token()
        if is_token_error(token):
            logger.error(f"get_category_suggestions: Token acquisition failed: {token}")
            return f"Token acquisition failed. Details: {token}"

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        params = {"q": query}
        url = "https://api.ebay.com/commerce/taxonomy/v1/category_tree/3/get_category_suggestions"
        logger.debug(f"get_category_suggestions: Requesting URL: {url} with params: {params}")
        logger.debug(f"get_category_suggestions: Headers: {{'Authorization': 'Bearer {token[:20]}...', ...}}")
        try:
            response = await client.get(url, headers=headers, params=params)
            logger.debug(f"get_category_suggestions: Response status: {response.status_code}")
            if response.status_code != 200:
                error_msg = f"eBay Taxonomy API request (get_category_suggestions) failed with status code {response.status_code}: {response.text}"
                logger.error(error_msg)
                return error_msg
            logger.info("get_category_suggestions: Successfully fetched category suggestions.")
            return response.text
        except Exception as e:
            error_msg = f"Error occurred during get_category_suggestions eBay API request: {e}"
            logger.exception(error_msg)
            return error_msg

@mcp.tool()
async def get_item_aspects_for_category(category_id: str) -> str:
    """Get item aspects for a specific category from eBay Taxonomy API.
    
    Args:
        category_id: The eBay category ID to get aspects for.
    """
    logger.info(f"Executing get_item_aspects_for_category MCP tool with category_id='{category_id}'.")
    async with httpx.AsyncClient() as client:
        token = await get_ebay_access_token()
        if is_token_error(token):
            logger.error(f"get_item_aspects_for_category: Token acquisition failed: {token}")
            return f"Token acquisition failed. Details: {token}"

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        url = f"https://api.ebay.com/commerce/taxonomy/v1/category_tree/3/get_item_aspects_for_category"
        logger.debug(f"get_item_aspects_for_category: Requesting URL: {url} with category_id: {category_id}")
        logger.debug(f"get_item_aspects_for_category: Headers: {{'Authorization': 'Bearer {token[:20]}...', ...}}")
        try:
            response = await client.get(url, headers=headers, params={"category_id": category_id})
            logger.debug(f"get_item_aspects_for_category: Response status: {response.status_code}")
            if response.status_code != 200:
                error_msg = f"eBay Taxonomy API request (get_item_aspects_for_category) failed with status code {response.status_code}: {response.text}"
                logger.error(error_msg)
                return error_msg
            logger.info("get_item_aspects_for_category: Successfully fetched item aspects.")
            return response.text
        except Exception as e:
            error_msg = f"Error occurred when fetching category aspects: {e}"
            logger.exception(error_msg)
            return error_msg

@mcp.tool()
async def get_offer_by_sku(sku: str) -> str:
    """Get offer details for a specific SKU from eBay Sell Inventory API.
    
    Args:
        sku: The seller-defined SKU (Stock Keeping Unit) of the offer.
    """
    logger.info(f"Executing get_offer_by_sku MCP tool with SKU='{sku}'.")
    async with httpx.AsyncClient() as client:
        token = await get_ebay_access_token()
        if is_token_error(token):
            logger.error(f"get_offer_by_sku: Token acquisition failed: {token}")
            return f"Token acquisition failed. Details: {token}"
        
        logger.info(f"get_offer_by_sku: Attempting API call with token (first 10 chars): {token[:10]}... for SKU: {sku}")
        
        logger.debug(f"get_offer_by_sku: Using token (first 10 chars): {token[:10]}...")
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-EBAY-C-MARKETPLACE-ID": "EBAY_GB",  # UK marketplace
            # The X-EBAY-C-ENDUSERCTX header might be optional or context-specific.
            # If it's causing issues or not always needed, it can be commented out or made conditional.
            # "X-EBAY-C-ENDUSERCTX": f"affiliateCampaignId=<e9e5b23f2c3d4f8a9f5c6d7e8f9a0b1>,affiliateReferenceId=<123456789>",
        }
        
        base_url = "https://api.ebay.com/sell/inventory/v1/offer"
        
        # For debugging, log headers carefully, especially the Authorization token.
        # Avoid logging the full token in production if possible, or only log a portion.
        # Create a sanitized version of headers for logging if necessary.
        log_headers = headers.copy()
        if 'Authorization' in log_headers:
            log_headers['Authorization'] = f"Bearer {token[:20]}...<truncated>"
        logger.debug(f"get_offer_by_sku: Headers for API call: {log_headers}")
        logger.debug(f"get_offer_by_sku: Request URL for direct SKU lookup: {base_url}?sku={sku}")
        
        try:
            logger.info(f"get_offer_by_sku: Attempting direct offer lookup for SKU: {sku}")
            response = await client.get(base_url, headers=headers, params={"sku": sku})
            
            logger.info(f"get_offer_by_sku: Direct SKU lookup response status: {response.status_code}")
            logger.debug(f"get_offer_by_sku: Direct SKU lookup response headers: {dict(response.headers)}")
            # Log response text carefully, it can be large or contain sensitive info.
            response_text_snippet = response.text[:500] if response.text else "[Empty Response Body]"
            logger.debug(f"get_offer_by_sku: Direct SKU lookup response text (first 500 chars): {response_text_snippet}...")

            # Original code had a 403 check for an alternative approach.
            # The primary issue reported is 401 (Unauthorized).
            # If a 401 occurs, the token is invalid for this API, possibly due to missing scopes (e.g., sell.inventory).
            # The alternative approach of listing offers first would likely also fail with a 401 if the scope is missing.
            if response.status_code == 403: # Or other client errors like 404 if SKU not found directly
                logger.warning(f"get_offer_by_sku: Direct SKU lookup failed with {response.status_code}. Trying alternative approach (listing offers to find ID). This might also fail if the root cause is token scope.")
                
                list_offers_params = {"sku": sku, "limit": 1}
                logger.debug(f"get_offer_by_sku: Listing offers with params: {list_offers_params}")
                offers_response = await client.get(base_url, headers=headers, params=list_offers_params)
                
                logger.info(f"get_offer_by_sku: Offer list response status: {offers_response.status_code}")
                offers_response_text_snippet = offers_response.text[:500] if offers_response.text else "[Empty Response Body]"
                logger.debug(f"get_offer_by_sku: Offer list response text (first 500 chars): {offers_response_text_snippet}...")
                
                if offers_response.status_code == 200:
                    offers_data = offers_response.json()
                    logger.debug(f"get_offer_by_sku: Parsed offers data from listing: {offers_data}")
                    
                    if offers_data.get('offers') and len(offers_data['offers']) > 0:
                        offer_id = offers_data['offers'][0].get('offerId')
                        if offer_id:
                            logger.info(f"get_offer_by_sku: Found offer ID: {offer_id} from listing. Fetching details.")
                            offer_detail_url = f"{base_url}/{offer_id}"
                            logger.debug(f"get_offer_by_sku: Requesting offer details from URL: {offer_detail_url}")
                            response = await client.get(offer_detail_url, headers=headers) # Re-assign response
                            logger.info(f"get_offer_by_sku: Offer details response status (after listing): {response.status_code}")
                            response_text_snippet_detail = response.text[:500] if response.text else "[Empty Response Body]"
                            logger.debug(f"get_offer_by_sku: Offer details response text (first 500 chars): {response_text_snippet_detail}...")
                        else:
                            logger.warning("get_offer_by_sku: 'offerId' not found in listed offer. Original direct lookup response will be used.")
                            # If offerId is not found, the original 'response' object (from direct SKU lookup) is still the one that dictates the outcome.
                    else:
                        logger.warning(f"get_offer_by_sku: No offers found in the listing for SKU {sku}, even though listing status was 200. Original direct lookup response will be used.")
                else:
                    logger.error(f"get_offer_by_sku: Failed to list offers (alternative approach), status: {offers_response.status_code}. Original direct lookup response will be used.")
            
            if response.status_code != 200:
                error_msg = f"eBay Sell Inventory API request (get_offer_by_sku) failed with status code {response.status_code}: {response.text}"
                logger.error(error_msg)
                # Attempt to parse and log specific eBay errors if the response is JSON
                try:
                    error_json = response.json()
                    if "errors" in error_json:
                        for err_idx, err_detail in enumerate(error_json["errors"]):
                            logger.error(f"get_offer_by_sku: eBay API Error Detail #{err_idx + 1}: ID {err_detail.get('errorId')}, Domain: {err_detail.get('domain')}, Category: {err_detail.get('category')}, Message: {err_detail.get('message')}, LongMessage: {err_detail.get('longMessage')}")
                except ValueError: # Handles cases where response.text is not valid JSON
                    logger.debug("get_offer_by_sku: Response body was not JSON, full text already logged.")
                return error_msg
            
            logger.info(f"get_offer_by_sku: Successfully fetched offer for SKU {sku}.")
            return response.text
            
        except Exception as e:
            error_msg = f"An unexpected error occurred when fetching offer by SKU '{sku}': {str(e)}"
            logger.exception(error_msg) # Log full traceback
            return error_msg


if __name__ == "__main__":
    logger.info("Starting FastMCP server with stdio transport...")
    logger.info("To test authentication, use the MCP client to call the 'test_auth' function or other tools.")
    logger.info(f"Logging to: {LOG_FILE_PATH}")
    mcp.run_stdio_server()
