"""
Database Tools MCP Server - Contains database utility tools
"""
import logging
import os
import sys
import json
from fastmcp import FastMCP

# Add the project root directory to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(project_root)

# Get logger
logger = logging.getLogger(__name__)

# Create Database Tools MCP server
database_mcp = FastMCP("Database Tools API")

@database_mcp.tool()
def mock_db_query(query: str) -> str:
    """Simulates a database query (for testing purposes)
    
    Args:
        query: SQL query to execute
    """
    logger.info(f"Executing mock_db_query with query: {query}")
    
    try:
        # This is just a mock function that simulates a database query
        if "SELECT" in query.upper():
            # Simulate a SELECT query
            result = {
                "status": "success",
                "rows": [
                    {"id": 1, "name": "Test Item 1", "price": 10.99},
                    {"id": 2, "name": "Test Item 2", "price": 20.99},
                    {"id": 3, "name": "Test Item 3", "price": 30.99}
                ],
                "rowCount": 3
            }
            return json.dumps(result)
        elif "INSERT" in query.upper():
            # Simulate an INSERT query
            result = {
                "status": "success",
                "insertId": 4,
                "rowsAffected": 1
            }
            return json.dumps(result)
        elif "UPDATE" in query.upper():
            # Simulate an UPDATE query
            result = {
                "status": "success",
                "rowsAffected": 1
            }
            return json.dumps(result)
        elif "DELETE" in query.upper():
            # Simulate a DELETE query
            result = {
                "status": "success",
                "rowsAffected": 1
            }
            return json.dumps(result)
        else:
            # Unknown query type
            result = {
                "status": "error",
                "message": "Unknown query type"
            }
            return json.dumps(result)
    except Exception as e:
        logger.error(f"Error in mock_db_query: {str(e)}")
        result = {
            "status": "error",
            "message": str(e)
        }
        return json.dumps(result)
