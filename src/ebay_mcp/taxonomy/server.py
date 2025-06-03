"""
eBay Taxonomy MCP Server - Handles eBay Taxonomy APIs
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

# Import taxonomy-related models
from models.ebay.taxonomy import CategorySuggestionRequest, CategorySuggestion, CategorySuggestionResponse
from models.ebay.taxonomy import ItemAspectsRequest, Aspect, ItemAspectsResponse
from models.mcp_tools import CategorySuggestionsParams, ItemAspectsParams

# Import the common helper function for eBay API calls
from utils.api_utils import execute_ebay_api_call, is_token_error
from utils.debug_httpx import create_debug_client

# Load environment variables
load_dotenv()

# Determine if we're in DEBUG mode
DEBUG_MODE = os.getenv('MCP_LOG_LEVEL', 'NORMAL').upper() == 'DEBUG'

# Get logger
logger = logging.getLogger(__name__)

# Create Taxonomy MCP server
taxonomy_mcp = FastMCP("eBay Taxonomy API")

@taxonomy_mcp.tool()
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
        
        # Use the enhanced debug client
        async with create_debug_client() as client:
            result = await execute_ebay_api_call("get_category_suggestions", client, _api_call)
            
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

@taxonomy_mcp.tool()
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
        
        # Use the enhanced debug client
        async with create_debug_client() as client:
            result = await execute_ebay_api_call("get_item_aspects_for_category", client, _api_call)
            
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
