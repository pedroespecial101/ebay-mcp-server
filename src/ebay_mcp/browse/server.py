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
from models.ebay.browse import SearchRequest, SearchResult, SearchResponse, ItemSummary
from models.mcp_tools import SearchEbayItemsParams

# Import the common helper function for eBay API calls
from ebay_service import get_ebay_access_token
from utils.api_utils import execute_ebay_api_call, get_standard_ebay_headers
from utils.debug_httpx import create_debug_client

# Load environment variables
load_dotenv()

# Determine if we're in DEBUG mode
DEBUG_MODE = os.getenv('MCP_LOG_LEVEL', 'NORMAL').upper() == 'DEBUG'

# Get logger
logger = logging.getLogger(__name__)

# Create Browse MCP server
browse_mcp = FastMCP("eBay Browse API")

@browse_mcp.tool()
async def search_ebay_items(query: str, limit: int = 10) -> str:
    """Search items on eBay using Browse API"""
    logger.info(f"Executing search_ebay_items MCP tool with query='{query}', limit={limit}.")
    
    # Validate parameters using Pydantic model
    try:
        params = SearchEbayItemsParams(query=query, limit=limit)
        
        async def _api_call(access_token: str, client: httpx.AsyncClient):
            # Use standardized eBay API headers
            headers = get_standard_ebay_headers(access_token)
            api_params = {"q": params.query, "limit": params.limit}
            url = "https://api.ebay.com/buy/browse/v1/item_summary/search"
            logger.debug(f"search_ebay_items: Requesting URL: {url} with params: {api_params} using token {access_token[:10]}...")
            
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
