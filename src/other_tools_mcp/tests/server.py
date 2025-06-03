"""
Test Tools MCP Server - Contains testing utilities
"""
import logging
import os
import sys
from fastmcp import FastMCP

# Add the project root directory to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(project_root)

# Import models
from models.mcp_tools import AddToolParams, AddToolResponse

# Get logger
logger = logging.getLogger(__name__)

# Create Tests MCP server
tests_mcp = FastMCP("Test Tools API")

@tests_mcp.tool()
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
