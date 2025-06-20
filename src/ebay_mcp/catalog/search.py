"""
eBay Catalog MCP Server - Search by GTIN Functionality
"""
import logging
import os
import sys
import httpx
import json
from typing import Optional

# Add the project root directory to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(project_root)

from models.ebay.catalog import (
    CatalogSearchByGTINRequest,
    CatalogSearchByGTINResponse,
    ProductSearchResult
)
from utils.api_utils import execute_ebay_api_call, get_standard_ebay_headers
from utils.debug_httpx import create_debug_client

logger = logging.getLogger(__name__)

async def search_by_gtin_tool(catalog_mcp):
    """
    Register the search_by_gtin tool with the FastMCP server.
    
    Args:
        catalog_mcp: The FastMCP instance for the catalog tools
    """
    @catalog_mcp.tool()
    async def search_by_gtin(gtin: str) -> str:
        """Search the eBay catalog for products matching a specific GTIN.
        
        This tool allows you to search the eBay catalog using a Global Trade Item Number (GTIN),
        which can be an EAN, ISBN, or UPC. The API returns product details that match the provided GTIN.
        
        Args:
            gtin (str): The Global Trade Item Number (GTIN) to search for.
        
        Returns:
            str: A JSON string representing the CatalogSearchByGTINResponse.
        """
        logger.info(f"Executing search_by_gtin MCP tool: GTIN='{gtin}'")

        async def _api_call_logic(access_token: str, client: httpx.AsyncClient):
            # Set up API headers
            headers = get_standard_ebay_headers(access_token)
            headers['Accept'] = 'application/json'  # Ensure JSON response
            
            # URL encode special characters in the query parameters
            encoded_gtin = gtin.strip()
            
            # Build the URL
            url = f"https://api.ebay.com/commerce/catalog/v1_beta/product_summary/search?gtin={encoded_gtin}"
            logger.debug(f"search_by_gtin: URL: {url}")
            
            # Make the API call
            response = await client.get(url, headers=headers)
            log_headers = headers.copy()
            log_headers['Authorization'] = f"Bearer {access_token[:20]}...<truncated>"
            logger.debug(f"search_by_gtin: Headers: {log_headers}, URL: {url}")
            logger.debug(f"search_by_gtin: Response status: {response.status_code}, text: {response.text[:500]}...")
            
            # Raise for status to catch any HTTP errors
            response.raise_for_status()
            
            if response.status_code == 204 or not response.content:
                # No matching products found
                logger.info(f"search_by_gtin: No products found for GTIN '{gtin}'")
                return CatalogSearchByGTINResponse.success_response(
                    message=f"No products found for GTIN '{gtin}'",
                    status_code=204,
                    product_data=None
                ).model_dump_json(indent=2)
            
            # Parse the response
            response_data = response.json()
            product_search_result = ProductSearchResult.model_validate(response_data)
            
            message = "Search completed successfully."
            if product_search_result.product_summaries and len(product_search_result.product_summaries) > 0:
                product_count = len(product_search_result.product_summaries)
                message = f"Found {product_count} product(s) matching GTIN '{gtin}'."
                logger.info(f"search_by_gtin: {message}")
            else:
                message = f"No products found for GTIN '{gtin}', but search was successful."
                logger.info(f"search_by_gtin: {message}")
            
            return CatalogSearchByGTINResponse.success_response(
                message=message,
                status_code=response.status_code,
                product_data=product_search_result
            ).model_dump_json(indent=2)
        
        # Validate GTIN before making API call
        if not gtin or gtin.strip() == "":
            error_response = CatalogSearchByGTINResponse(
                success=False,
                message="GTIN cannot be empty",
                status_code=400
            )
            return error_response.model_dump_json(indent=2)
            
        try:
            async with create_debug_client() as client:
                # The execute_ebay_api_call handles token acquisition and basic error wrapping
                result_str = await execute_ebay_api_call(f"search_by_gtin_{gtin}", client, _api_call_logic)
                return result_str
        except httpx.HTTPStatusError as hse:
            logger.error(f"HTTPStatusError in search_by_gtin for GTIN '{gtin}': {hse.response.status_code} - {hse.response.text[:500]}")
            error_details = hse.response.text
            try:
                error_json = hse.response.json()
                error_details = error_json.get('errors', [{}])[0].get('message', hse.response.text)
            except Exception:
                pass  # Keep raw text if not JSON
            return CatalogSearchByGTINResponse.error_response(
                message=f"eBay API Error ({hse.response.status_code}): {error_details}",
                status_code=hse.response.status_code
            ).model_dump_json(indent=2)
        except Exception as e:
            logger.error(f"Error in search_by_gtin: {e}")
            error_response = CatalogSearchByGTINResponse(
                success=False,
                message=f"Error searching eBay catalog for GTIN '{gtin}': {str(e)}",
                status_code=500
            )
            return error_response.model_dump_json(indent=2)
