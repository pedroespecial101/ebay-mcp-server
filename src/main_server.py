"""
Main MCP Server - Dynamically mounts all sub-servers
"""
import os
import sys
import logging
import logging.handlers

# Add the project root directory to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# --- Centralized Logging Configuration --- 
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
LOG_FILE_PATH = os.path.join(LOG_DIR, 'fastmcp_server.log')

# Ensure log directory exists
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# Get the root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)  # Set root logger level (can be overridden by handlers)

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
timed_handler.setLevel(logging.DEBUG)  # Set handler level, e.g., DEBUG or INFO

# Add handler to the root logger
root_logger.addHandler(timed_handler)

logger = logging.getLogger(__name__)  # Get a logger for this specific module
logger.info("Logging configured with TimedRotatingFileHandler.")
# --- End of Centralized Logging Configuration ---

from fastmcp import FastMCP

# Import all sub-servers
from ebay_mcp.auth.server import auth_mcp
from ebay_mcp.browse.server import browse_mcp
from ebay_mcp.taxonomy.server import taxonomy_mcp
from ebay_mcp.inventory.server import inventory_mcp
from other_tools_mcp.tests.server import tests_mcp
from other_tools_mcp.database.server import database_mcp

# Create the main MCP server
mcp = FastMCP("eBay API")

# Mount sub-servers
def mount_servers():
    """Mount all sub-servers to the main MCP server"""
    logger.info("Mounting all sub-servers")
    
    # Mount auth tools
    mcp.mount("auth", auth_mcp)
    logger.info("Mounted auth MCP server")
    
    # Mount browse API tools
    mcp.mount("browseAPI", browse_mcp)
    logger.info("Mounted browse API MCP server")
    
    # Mount taxonomy API tools
    mcp.mount("taxonomyAPI", taxonomy_mcp)
    logger.info("Mounted taxonomy API MCP server")
    
    # Mount inventory API tools
    mcp.mount("inventoryAPI", inventory_mcp)
    logger.info("Mounted inventory API MCP server")
    
    # Mount test tools
    mcp.mount("tests", tests_mcp)
    logger.info("Mounted tests MCP server")
    
    # Mount database tools
    mcp.mount("database", database_mcp)
    logger.info("Mounted database MCP server")
    
    logger.info("All sub-servers mounted successfully")

# Mount all servers
mount_servers()

# When running this file directly, start the MCP server
if __name__ == "__main__":
    logger.info("Starting FastMCP server with stdio transport...")
    logger.info("Server is configured with dynamically mounted sub-servers")
    main_mcp.run()
