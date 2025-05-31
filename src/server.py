from fastmcp import FastMCP
import httpx
import os
import sys
import logging
import logging.handlers
import json
from typing import Any, Dict, List, Optional, Union

# Add the src directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import Pydantic models
from src.models.base import EbayResponse
from src.models.config.settings import EbayAuthConfig, ServerConfig
from src.models.ebay.browse import SearchRequest, SearchResult, SearchResponse
from src.models.ebay.taxonomy import CategorySuggestionRequest, CategorySuggestion, CategorySuggestionResponse
from src.models.ebay.taxonomy import ItemAspectsRequest, Aspect, ItemAspectsResponse
from src.models.ebay.inventory import OfferRequest, OfferDetails, OfferResponse
from src.models.ebay.inventory import UpdateOfferRequest, WithdrawOfferRequest, ListingFeeRequest, ListingFeeResponse
from src.models.mcp_tools import AddToolParams, AddToolResponse
from src.models.mcp_tools import SearchEbayItemsParams, CategorySuggestionsParams, ItemAspectsParams, OfferBySkuParams
from src.models.mcp_tools import UpdateOfferParams, WithdrawOfferParams, ListingFeesParams
from src.models.mcp_tools import TestAuthResponse, TriggerEbayLoginResponse
from src.models.auth import LoginResult

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
from ebay_auth.ebay_auth import initiate_user_login # For triggering login flow

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

# MCP Tool to trigger eBay login
@mcp.tool()
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


# Add an addition tool
@mcp.tool()
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

@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""
    logger.debug(f"Executing add MCP tool with a={a}, b={b}")
    
    # Create and validate parameters using Pydantic model
    try:
        params = AddToolParams(a=a, b=b)
        result = params.a + params.b
        response = AddToolResponse.success_response(result)
        return response.data
    except Exception as e:
        logger.error(f"Error in add tool: {str(e)}")
        return AddToolResponse.error_response(f"Error: {str(e)}").error_message or 0


# Add a tool to search eBay items using Browse API
@mcp.tool()
async def search_ebay_items(query: str, limit: int = 10) -> str:
    """Search items on eBay using Browse API"""
    logger.info(f"Executing search_ebay_items MCP tool with query='{query}', limit={limit}.")
    
    # Validate parameters using Pydantic model
    try:
        params = SearchEbayItemsParams(query=query, limit=limit)
        
        async def _api_call(access_token: str, client: httpx.AsyncClient):
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }
            api_params = {"q": params.query, "limit": params.limit}
            url = "https://api.ebay.com/buy/browse/v1/item_summary/search"
            logger.debug(f"search_ebay_items: Requesting URL: {url} with params: {api_params} using token {access_token[:10]}...")
            
            response = await client.get(url, headers=headers, params=api_params)
            logger.debug(f"search_ebay_items: Response status: {response.status_code}")
            response.raise_for_status() # Crucial for _execute_ebay_api_call to handle HTTP errors
            logger.info("search_ebay_items: Successfully fetched items.")
            return response.text
        
        async with httpx.AsyncClient() as client:
            result = await _execute_ebay_api_call("search_ebay_items", client, _api_call)
            
            # Try to parse the response as a SearchResult
            try:
                if not result.startswith('Token acquisition failed') and not result.startswith('HTTPX RequestError'):
                    result_json = json.loads(result)
                    search_result = SearchResult(
                        total=result_json.get('total', 0),
                        items=[ItemSummary(
                            item_id=item.get('itemId', ''),
                            title=item.get('title', ''),
                            image_url=item.get('image', {}).get('imageUrl'),
                            price=item.get('price'),
                            seller=item.get('seller'),
                            condition=item.get('condition'),
                            item_web_url=item.get('itemWebUrl')
                        ) for item in result_json.get('itemSummaries', [])],
                        href=result_json.get('href'),
                        next_page=result_json.get('next'),
                        prev_page=result_json.get('prev'),
                        limit=result_json.get('limit'),
                        offset=result_json.get('offset')
                    )
                    logger.info(f"Parsed search results: {search_result.total} items found")
                    # Return the original JSON for backward compatibility
                    return result
            except Exception as e:
                logger.warning(f"Failed to parse search results as SearchResult: {str(e)}")
            
            return result
    except Exception as e:
        logger.error(f"Error in search_ebay_items: {str(e)}")
        return f"Error in search parameters: {str(e)}"

@mcp.tool()
async def get_category_suggestions(query: str) -> str:
    """Get category suggestions from eBay Taxonomy API for the UK catalogue."""
    logger.info(f"Executing get_category_suggestions MCP tool with query='{query}'.")
    
    # Validate parameters using Pydantic model
    try:
        params = CategorySuggestionsParams(query=query)
        
        async def _api_call(access_token: str, client: httpx.AsyncClient):
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }
            api_params = {"q": params.query}
            url = "https://api.ebay.com/commerce/taxonomy/v1/category_tree/3/get_category_suggestions"
            logger.debug(f"get_category_suggestions: Requesting URL: {url} with params: {api_params} using token {access_token[:10]}...")
            
            response = await client.get(url, headers=headers, params=api_params)
            logger.debug(f"get_category_suggestions: Response status: {response.status_code}")
            response.raise_for_status()
            logger.info("get_category_suggestions: Successfully fetched category suggestions.")
            return response.text
        
        async with httpx.AsyncClient() as client:
            result = await _execute_ebay_api_call("get_category_suggestions", client, _api_call)
            
            # Try to parse the response as a CategorySuggestionResponse
            try:
                if not result.startswith('Token acquisition failed') and not result.startswith('HTTPX RequestError'):
                    result_json = json.loads(result)
                    suggestions = []
                    for suggestion in result_json.get('categorySuggestions', []):
                        category = suggestion.get('category', {})
                        suggestions.append(CategorySuggestion(
                            category_id=category.get('categoryId', ''),
                            category_name=category.get('categoryName', ''),
                            category_tree_node_level=category.get('categoryTreeNodeLevel'),
                            relevancy=suggestion.get('relevancy'),
                            category_tree_id=result_json.get('categoryTreeId'),
                            leaf_category=category.get('leafCategory', False)
                        ))
                    
                    suggestion_response = CategorySuggestionResponse.success_response(suggestions)
                    logger.info(f"Parsed category suggestions: {len(suggestions)} suggestions found")
                    # Return the original JSON for backward compatibility
                    return result
            except Exception as e:
                logger.warning(f"Failed to parse category suggestions: {str(e)}")
            
            return result
    except Exception as e:
        logger.error(f"Error in get_category_suggestions: {str(e)}")
        return f"Error in category suggestion parameters: {str(e)}"

@mcp.tool()
async def get_item_aspects_for_category(category_id: str) -> str:
    """Get item aspects for a specific category from eBay Taxonomy API.
    
    Args:
        category_id: The eBay category ID to get aspects for.
    """
    logger.info(f"Executing get_item_aspects_for_category MCP tool with category_id='{category_id}'.")
    
    # Validate parameters using Pydantic model
    try:
        params = ItemAspectsParams(category_id=category_id)
        
        async def _api_call(access_token: str, client: httpx.AsyncClient):
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }
            url = f"https://api.ebay.com/commerce/taxonomy/v1/category_tree/3/get_item_aspects_for_category"
            logger.debug(f"get_item_aspects_for_category: Requesting URL: {url} with category_id: {params.category_id} using token {access_token[:10]}...")
            
            response = await client.get(url, headers=headers, params={"category_id": params.category_id})
            logger.debug(f"get_item_aspects_for_category: Response status: {response.status_code}")
            response.raise_for_status()
            logger.info("get_item_aspects_for_category: Successfully fetched item aspects.")
            return response.text
        
        async with httpx.AsyncClient() as client:
            result = await _execute_ebay_api_call("get_item_aspects_for_category", client, _api_call)
            
            # Try to parse the response as an ItemAspectsResponse
            try:
                if not result.startswith('Token acquisition failed') and not result.startswith('HTTPX RequestError'):
                    result_json = json.loads(result)
                    aspects = []
                    for aspect_json in result_json.get('aspects', []):
                        # Convert aspect metadata to Pydantic model
                        aspect = Aspect(
                            aspect_id=aspect_json.get('localizedAspectName'),
                            name=aspect_json.get('localizedAspectName', ''),
                            aspect_type=aspect_json.get('aspectConstraint', {}).get('aspectMode', ''),
                            required=aspect_json.get('aspectConstraint', {}).get('aspectRequired', False),
                            aspect_values=aspect_json.get('aspectValues', []),
                            usage=aspect_json.get('aspectConstraint', {}).get('aspectUsage', ''),
                            min_values=aspect_json.get('aspectConstraint', {}).get('itemToAspectCardinality', {}).get('minimum', 0),
                            max_values=aspect_json.get('aspectConstraint', {}).get('itemToAspectCardinality', {}).get('maximum', 0),
                            confidence=aspect_json.get('aspectConstraint', {}).get('confidenceThreshold', 0),
                            value_format=aspect_json.get('aspectConstraint', {}).get('valueConstraint', {}).get('applicableForLocalizedAspectName', '')
                        )
                        aspects.append(aspect)
                    
                    aspects_response = ItemAspectsResponse.success_response(aspects)
                    logger.info(f"Parsed item aspects: {len(aspects)} aspects found for category {params.category_id}")
                    # Return the original JSON for backward compatibility
                    return result
            except Exception as e:
                logger.warning(f"Failed to parse item aspects: {str(e)}")
            
            return result
    except Exception as e:
        logger.error(f"Error in get_item_aspects_for_category: {str(e)}")
        return f"Error in item aspects parameters: {str(e)}"

@mcp.tool()
async def get_offer_by_sku(sku: str) -> str:
    """Get offer details for a specific SKU from eBay Sell Inventory API.
    
    Args:
        sku: The seller-defined SKU (Stock Keeping Unit) of the offer.
    """
    logger.info(f"Executing get_offer_by_sku MCP tool with SKU='{sku}'.")
    
    # Validate parameters using Pydantic model
    try:
        params = OfferBySkuParams(sku=sku)
        
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
            logger.debug(f"get_offer_by_sku: Request URL for direct SKU lookup: {base_url}?sku={params.sku} using token {access_token[:10]}...")
    
            # Initial attempt: Direct SKU lookup
            response = await client.get(base_url, headers=headers, params={"sku": params.sku})
            logger.info(f"get_offer_by_sku: Direct SKU lookup response status: {response.status_code}")
            response_text_snippet = response.text[:500] if response.text else "[Empty Response Body]"
            logger.debug(f"get_offer_by_sku: Direct SKU lookup response text (first 500 chars): {response_text_snippet}...")
    
            # If direct lookup fails with 403/404 (or other client error that's not 401, which is handled by _execute_ebay_api_call),
            # try the alternative approach of listing offers.
            # Note: response.raise_for_status() will be called *after* this block if status is still not 200.
            if response.status_code in [403, 404]: 
                logger.warning(f"get_offer_by_sku: Direct SKU lookup failed with {response.status_code}. Trying alternative approach (listing offers).")
                
                list_offers_params = {"sku": params.sku, "limit": 1}
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
                        logger.warning(f"get_offer_by_sku: No offers found in the listing for SKU {params.sku}. Original direct lookup response will be used.")
                else:
                    logger.error(f"get_offer_by_sku: Failed to list offers (alternative approach), status: {offers_response.status_code}. Original direct lookup response will be used.")
            
            # After potential fallback, raise for status on the final 'response' object.
            # This allows _execute_ebay_api_call to handle 401s from either direct or fallback calls.
            response.raise_for_status()
            
            logger.info(f"get_offer_by_sku: Successfully fetched offer for SKU {params.sku}.")
            return response.text
        
        async with httpx.AsyncClient() as client:
            result = await _execute_ebay_api_call("get_offer_by_sku", client, _api_call)
            
            # Try to parse the response as an OfferResponse
            try:
                if not result.startswith('Token acquisition failed') and not result.startswith('HTTPX RequestError'):
                    result_json = json.loads(result)
                    
                    # Extract offer details from the response
                    if 'offers' in result_json and len(result_json['offers']) > 0:
                        offer_data = result_json['offers'][0]
                    else:
                        offer_data = result_json
                    
                    # Create Pydantic model for the offer
                    offer_details = OfferDetails(
                        offer_id=offer_data.get('offerId', ''),
                        sku=offer_data.get('sku', params.sku),
                        marketplace_id=offer_data.get('marketplaceId', 'EBAY_GB'),
                        format=offer_data.get('format', ''),
                        available_quantity=offer_data.get('availableQuantity', 0),
                        price=offer_data.get('price', {}),
                        listing_policies=offer_data.get('listingPolicies', {}),
                        listing_description=offer_data.get('listingDescription', ''),
                        listing_status=offer_data.get('listingStatus', ''),
                        tax=offer_data.get('tax', {}),
                        category_id=offer_data.get('categoryId', ''),
                        merchant_location_key=offer_data.get('merchantLocationKey', ''),
                        inventory_location=offer_data.get('inventoryLocation', ''),
                        listing_id=offer_data.get('listingId', '')
                    )
                    
                    offer_response = OfferResponse.success_response(offer_details)
                    logger.info(f"Parsed offer details for SKU {params.sku}: {offer_details.offer_id}")
                    # Return the original JSON for backward compatibility
                    return result
            except Exception as e:
                logger.warning(f"Failed to parse offer details: {str(e)}")
            
            return result
    except Exception as e:
        logger.error(f"Error in get_offer_by_sku: {str(e)}")
        return f"Error in offer parameters: {str(e)}"


@mcp.tool()
async def update_offer(offer_id: str, sku: str, marketplace_id: str = "EBAY_GB", price: float = None, available_quantity: int = None) -> str:
    """Update an existing offer with new price and/or quantity.
    
    Args:
        offer_id: The unique identifier of the offer to update.
        sku: The seller-defined SKU (Stock Keeping Unit) of the offer.
        marketplace_id: The eBay marketplace ID (default: EBAY_GB).
        price: New price for the offer (optional).
        available_quantity: New quantity for the offer (optional).
    """
    logger.info(f"Executing update_offer MCP tool with offer_id='{offer_id}', sku='{sku}'")
    
    # Validate parameters using Pydantic model
    try:
        params = UpdateOfferParams(
            offer_id=offer_id,
            sku=sku,
            marketplace_id=marketplace_id,
            price=price,
            available_quantity=available_quantity
        )
        
        # Check if at least one update field is specified
        if params.price is None and params.available_quantity is None:
            return "Error: At least one of price or available_quantity must be specified."

        async def _api_call(access_token: str, client: httpx.AsyncClient):
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "X-EBAY-C-MARKETPLACE-ID": params.marketplace_id,
                "Accept-Language": "en-GB"
            }
            
            # First, get the current offer details to ensure we have all required fields
            get_url = f"https://api.ebay.com/sell/inventory/v1/offer/{params.offer_id}"
            logger.debug(f"update_offer: Getting current offer details from: {get_url}")
            
            get_response = await client.get(get_url, headers=headers)
            get_response.raise_for_status()  # This will be caught by _execute_ebay_api_call if there's an error
            
            current_offer = get_response.json()
            logger.debug(f"update_offer: Successfully retrieved current offer details for {params.sku}")
            
            # Create an update request based on the current offer
            update_request = UpdateOfferRequest(
                offer_id=params.offer_id,
                sku=params.sku,
                marketplace_id=params.marketplace_id,
                format=current_offer.get('format', 'FIXED_PRICE'),
                available_quantity=params.available_quantity if params.available_quantity is not None else current_offer.get('availableQuantity'),
                category_id=current_offer.get('categoryId', ''),
                listing_policies=current_offer.get('listingPolicies', {}),
                merchant_location_key=current_offer.get('merchantLocationKey', ''),
                pricing_summary=current_offer.get('pricingSummary', {})
            )
            
            # Update price if provided
            if params.price is not None:
                # Ensure pricing structure exists
                if not update_request.pricing_summary:
                    update_request.pricing_summary = {}
                if 'price' not in update_request.pricing_summary:
                    update_request.pricing_summary['price'] = {}
                
                # Update price value
                update_request.pricing_summary['price']['value'] = str(params.price)
                # Ensure currency exists
                if 'currency' not in update_request.pricing_summary['price']:
                    update_request.pricing_summary['price']['currency'] = "GBP"  # Default to GBP
            
            # Convert Pydantic model to dict for the API request
            update_payload = update_request.model_dump(exclude_none=True)
            
            # Make the update call
            update_url = f"https://api.ebay.com/sell/inventory/v1/offer/{params.offer_id}"
            logger.debug(f"update_offer: Sending PUT request to: {update_url}")
            logger.debug(f"update_offer: Request payload: {update_payload}")
            
            update_response = await client.put(update_url, headers=headers, json=update_payload)
            update_response.raise_for_status()
            
            logger.info(f"update_offer: Successfully updated offer {params.offer_id} for SKU {params.sku}")
            return update_response.text
        
        async with httpx.AsyncClient() as client:
            result = await _execute_ebay_api_call("update_offer", client, _api_call)
            
            # Try to parse the response if available
            try:
                if not result.startswith('Token acquisition failed') and not result.startswith('HTTPX RequestError'):
                    # For successful updates, we typically get an empty response or a status object
                    if result and len(result.strip()) > 0:
                        result_json = json.loads(result)
                        logger.info(f"Parsed update response: {result_json}")
                    else:
                        logger.info(f"Empty success response for offer update {params.offer_id}")
            except Exception as e:
                logger.warning(f"Failed to parse update response: {str(e)}")
            
            return result
    except Exception as e:
        logger.error(f"Error in update_offer: {str(e)}")
        return f"Error in update offer parameters: {str(e)}"


@mcp.tool()
async def withdraw_offer(offer_id: str) -> str:
    """Withdraw (delete) an existing offer from eBay.
    
    Args:
        offer_id: The unique identifier of the offer to withdraw.
    """
    logger.info(f"Executing withdraw_offer MCP tool with offer_id='{offer_id}'")
    
    # Validate parameters using Pydantic model
    try:
        params = WithdrawOfferParams(offer_id=offer_id)
        
        async def _api_call(access_token: str, client: httpx.AsyncClient):
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "X-EBAY-C-MARKETPLACE-ID": "EBAY_GB",
                "Accept-Language": "en-GB"
            }
            
            # Create a withdraw request using the Pydantic model
            withdraw_request = WithdrawOfferRequest(offer_id=params.offer_id)
            
            base_url = f"https://api.ebay.com/sell/inventory/v1/offer/{params.offer_id}/withdraw"
            logger.debug(f"withdraw_offer: Making POST request to: {base_url}")
            
            response = await client.post(base_url, headers=headers)
            response.raise_for_status()
            
            logger.info(f"withdraw_offer: Successfully withdrew offer {params.offer_id}")
            return response.text
        
        async with httpx.AsyncClient() as client:
            result = await _execute_ebay_api_call("withdraw_offer", client, _api_call)
            
            # Try to parse the response if available
            try:
                if not result.startswith('Token acquisition failed') and not result.startswith('HTTPX RequestError'):
                    # For successful withdrawals, we typically get an empty response or a status object
                    if result and len(result.strip()) > 0:
                        result_json = json.loads(result)
                        logger.info(f"Parsed withdraw response: {result_json}")
                    else:
                        logger.info(f"Empty success response for offer withdrawal {params.offer_id}")
            except Exception as e:
                logger.warning(f"Failed to parse withdraw response: {str(e)}")
            
            return result
    except Exception as e:
        logger.error(f"Error in withdraw_offer: {str(e)}")
        return f"Error in withdraw offer parameters: {str(e)}"


@mcp.tool()
async def get_listing_fees(offer_ids: list) -> str:
    """Get listing fees for unpublished offers.
    
    Args:
        offer_ids: List of offer IDs to get fees for (up to 250).
    """
    logger.info(f"Executing get_listing_fees MCP tool with {len(offer_ids)} offer IDs.")
    
    # Validate parameters using Pydantic model
    try:
        params = ListingFeesParams(offer_ids=offer_ids)
        
        # Validate the number of offer IDs
        if not params.offer_ids:
            return "Error: At least one offer ID must be provided."
        
        if len(params.offer_ids) > 250:
            return "Error: Maximum of 250 offer IDs can be processed at once."

        async def _api_call(access_token: str, client: httpx.AsyncClient):
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "X-EBAY-C-MARKETPLACE-ID": "EBAY_GB",
                "Accept-Language": "en-GB"
            }
            
            # Create listing fee request using the Pydantic model
            fee_request = ListingFeeRequest(
                offers=[{"offerId": offer_id} for offer_id in params.offer_ids]
            )
            
            # Convert to dict for API request
            payload = fee_request.model_dump()
            logger.debug(f"get_listing_fees: Request payload: {payload}")
            
            base_url = "https://api.ebay.com/sell/inventory/v1/offer/get_listing_fees"
            logger.debug(f"get_listing_fees: Making POST request to: {base_url}")
            
            response = await client.post(base_url, headers=headers, json=payload)
            response.raise_for_status()
            
            logger.info(f"get_listing_fees: Successfully retrieved listing fees")
            return response.text
        
        async with httpx.AsyncClient() as client:
            result = await _execute_ebay_api_call("get_listing_fees", client, _api_call)
            
            # Try to parse the response as a ListingFeeResponse
            try:
                if not result.startswith('Token acquisition failed') and not result.startswith('HTTPX RequestError'):
                    result_json = json.loads(result)
                    
                    # Create a ListingFeeResponse from the API response
                    fee_response = ListingFeeResponse(
                        fees=result_json.get('feeSummaries', []),
                        warnings=result_json.get('warnings', [])
                    )
                    
                    # Log a summary of the fees retrieved
                    fee_count = len(fee_response.fees)
                    logger.info(f"Parsed listing fees response: {fee_count} fee summaries retrieved")
                    
                    # Return the original JSON for backward compatibility
                    return result
            except Exception as e:
                logger.warning(f"Failed to parse listing fees response: {str(e)}")
            
            return result
    except Exception as e:
        logger.error(f"Error in get_listing_fees: {str(e)}")
        return f"Error in listing fees parameters: {str(e)}"


if __name__ == "__main__":
    logger.info("Starting FastMCP server with stdio transport...")
    logger.info("To test authentication, use the MCP client to call the 'test_auth' function or other tools.")
    logger.info(f"Logging to: {LOG_FILE_PATH}")
    logger.info("Attempting to call mcp.run()...")
    mcp.run(transport="stdio")
    logger.info("mcp.run() completed or exited.")
