"""
eBay Browse MCP Server - Handles eBay Browse APIs
"""
import logging
import os
import sys
import httpx
from fastmcp import FastMCP
import json
from dotenv import load_dotenv

# Add the project root directory to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(project_root)

# Import browse-related models
from models.mcp_tools import SearchEbayItemsParams, SearchByImageParams

# Import the common helper function for eBay API calls
from ebay_service import get_ebay_access_token
from utils.api_utils import execute_ebay_api_call, get_standard_ebay_headers, url_to_base64_image
from utils.debug_httpx import create_debug_client

# Load environment variables
if os.getenv("EBAY_TOKEN_STORE", "").lower() != "doppler":
    load_dotenv()

# Determine if we're in DEBUG mode
DEBUG_MODE = os.getenv('MCP_LOG_LEVEL', 'NORMAL').upper() == 'DEBUG'

# Get logger
logger = logging.getLogger(__name__)

# Create Browse MCP server
browse_mcp = FastMCP("eBay Browse API")

@browse_mcp.tool(
    annotations={"readOnlyHint": True, "openWorldHint": False, "destructiveHint": False}
)
async def search_ebay_items(query: str, limit: int = 10) -> str:
    """Legacy simple read-only live listing search.

    Prefer research_search_items for new market-research/listing workflows. This
    compatibility tool returns raw Browse API JSON for current live listings and
    asking prices only, not sold/completed comparables.
    """
    logger.info(f"Executing search_ebay_items MCP tool with query='{query}', limit={limit}.")

    # Validate parameters using Pydantic model
    try:
        params = SearchEbayItemsParams(query=query, limit=limit)

        async def _api_call(access_token: str, client: httpx.AsyncClient):
            # Use standardized eBay API headers
            headers = get_standard_ebay_headers(access_token)
            api_params = {"q": params.query, "limit": params.limit}
            url = "https://api.ebay.com/buy/browse/v1/item_summary/search"
            logger.debug(f"search_ebay_items: Requesting URL: {url} with params: {api_params}")

            response = await client.get(url, headers=headers, params=api_params)
            logger.debug(f"search_ebay_items: Response status: {response.status_code}")
            response.raise_for_status() # Crucial for execute_ebay_api_call to handle HTTP errors
            logger.info("search_ebay_items: Successfully fetched items.")
            return response.text

        # Use the enhanced debug client
        async with create_debug_client() as client:
            result = await execute_ebay_api_call("search_ebay_items", client, _api_call)

            # Try to parse the response as a SearchResult
            try:
                if not result.startswith('Token acquisition failed') and not result.startswith('HTTPX RequestError'):
                    result_json = json.loads(result)
                    logger.info(f"Parsed search results: {len(result_json.get('itemSummaries', []))} items found")
                    return result
            except Exception as e:
                logger.warning(f"Failed to parse search results: {str(e)}")

            return result
    except Exception as e:
        logger.error(f"Error in search_ebay_items: {str(e)}")
        return f"Error in search parameters: {str(e)}"


@browse_mcp.tool(
    annotations={"readOnlyHint": True, "openWorldHint": False, "destructiveHint": False}
)
async def search_by_image(params: SearchByImageParams) -> str:
    """Legacy simple visual-similarity search for live eBay listings.

    Prefer research_search_by_image for new market-research/listing workflows.
    This is a similarity-search tool, not an image viewer. It does not return the
    supplied image for model vision. To inspect photographs on one of the seller's
    own listings, use trading_view_item_images.

    Args:
        params (SearchByImageParams): Pydantic model containing image URL and optional filters
            - image_url: URL of the image to search with
            - category_ids: Optional category ID to limit search results
            - limit: Number of items to return (1-200)
            - filter: Optional filter criteria (e.g. price ranges, condition)
            - aspect_filter: Optional aspect filters (e.g. color, brand)

    Returns:
        JSON string with search results
    """
    logger.info(f"Executing search_by_image MCP tool with image_url='{params.image_url}', category_ids='{params.category_ids}', limit={params.limit}.")

    # The params are already validated by Pydantic
    try:

        async def _api_call(access_token: str, client: httpx.AsyncClient):
            # Use standardized eBay API headers
            headers = get_standard_ebay_headers(access_token)
            # Add Content-Type header required for POST requests
            headers['Content-Type'] = 'application/json'

            # Download image and convert to Base64
            try:
                logger.info("Downloading the image for eBay visual similarity search.")
                base64_image = await url_to_base64_image(params.image_url, client)
                logger.info("Successfully prepared the image for eBay visual similarity search.")
            except Exception as e:
                error_msg = f"Failed to download or convert image from URL: {str(e)}"
                logger.error(error_msg)
                return error_msg

            # Prepare query parameters (excluding image which goes in body)
            api_params = {}
            if params.category_ids:
                api_params["category_ids"] = params.category_ids
            if params.limit:
                api_params["limit"] = params.limit
            if params.filter:
                api_params["filter"] = params.filter
            if params.aspect_filter:
                api_params["aspect_filter"] = params.aspect_filter

            # Prepare request body with Base64 image data
            body = {"image": base64_image}

            url = "https://api.ebay.com/buy/browse/v1/item_summary/search_by_image"
            logger.debug(f"search_by_image: Requesting URL: {url} with params: {api_params}")

            # Use POST for image search with the image in the request body
            response = await client.post(url, headers=headers, params=api_params, json=body)
            logger.debug(f"search_by_image: Response status: {response.status_code}")
            response.raise_for_status() # Handle HTTP errors
            logger.info("search_by_image: Successfully fetched items.")
            return response.text

        # Use the enhanced debug client
        async with create_debug_client() as client:
            result = await execute_ebay_api_call("search_by_image", client, _api_call)

            # Try to parse the response as a SearchResult
            try:
                if not result.startswith('Token acquisition failed') and not result.startswith('HTTPX RequestError'):
                    result_json = json.loads(result)
                    logger.info(f"Parsed image search results: {len(result_json.get('itemSummaries', []))} items found")
                    return result
            except Exception as e:
                logger.warning(f"Failed to parse image search results: {str(e)}")

            return result
    except Exception as e:
        logger.error(f"Error in search_by_image: {str(e)}")
        return f"Error in search parameters: {str(e)}"
