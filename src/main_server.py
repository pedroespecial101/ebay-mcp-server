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
from dotenv import load_dotenv
import datetime

# Load environment variables from .env file
load_dotenv()

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
LOG_FILE_PATH = os.path.join(LOG_DIR, 'fastmcp_server.log')

# Ensure log directory exists
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# Set log level from environment variable, default to INFO if not set or invalid
log_level_str = os.getenv('MCP_LOG_LEVEL', 'NORMAL').upper()
if log_level_str == 'DEBUG':
    log_level = logging.DEBUG
else:  # NORMAL or any other value
    log_level = logging.INFO

# --- Custom Namer for RotatingFileHandler ---
def custom_log_namer(default_name):
    # default_name will be like /path/to/logs/fastmcp_server.log.1
    # We want to transform it to /path/to/logs/fastmcp_server.log.01_YYYY-MM-DD-HH-MM-SS
    base_filename, ext_num_str = os.path.splitext(default_name)
    if not ext_num_str or not ext_num_str[1:].isdigit():
        current_timestamp = datetime.datetime.now().strftime('%Y-%m-%d-%H:%M:%S')
        # Fallback: append timestamp to avoid overwriting or errors
        return f"{default_name}_{current_timestamp}"
    
    log_num = int(ext_num_str[1:])
    current_timestamp = datetime.datetime.now().strftime('%Y-%m-%d-%H:%M:%S')
    
    # Construct the new name: e.g., fastmcp_server.log.01_2023-10-27-15-30-00
    # The base_filename already contains the full path and the "fastmcp_server.log" part
    return f"{base_filename}.{log_num:02d}_{current_timestamp}"
# --- End of Custom Namer ---

# # Archive existing log file if it exists (Replaced by RotatingFileHandler)
# if os.path.exists(LOG_FILE_PATH):
#     timestamp = datetime.datetime.now().strftime('%Y-%m-%d-%H:%M:%S')
#     archive_path = f"{LOG_FILE_PATH}.{timestamp}"
#     try:
#         os.rename(LOG_FILE_PATH, archive_path)
#         print(f"Previous log archived to {archive_path}")
#     except Exception as e:
#         print(f"Failed to archive previous log: {e}")

# Get the root logger and clear any existing handlers
root_logger = logging.getLogger()
for handler in root_logger.handlers[:]:
    root_logger.removeHandler(handler)
root_logger.setLevel(logging.DEBUG)  # Base level for root logger

# Formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# File Handler for the main log file
file_handler = logging.handlers.RotatingFileHandler(
    LOG_FILE_PATH,
    maxBytes=10*1024*1024,  # 10 MB
    backupCount=9
)
file_handler.namer = custom_log_namer # Assign custom namer
file_handler.setFormatter(formatter)
file_handler.setLevel(log_level)

# Console Handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
console_handler.setLevel(log_level)

# Add handlers to the root logger
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)

# Create a module-specific logger
logger = logging.getLogger(__name__)
logger.info(f"Logging configured with level {log_level_str} ({logging.getLevelName(log_level)})")
logger.info(f"Log file location: {LOG_FILE_PATH}")
# --- End of Centralized Logging Configuration ---

from fastmcp import FastMCP

# Import all sub-servers
from ebay_mcp.auth.server import auth_mcp
from ebay_mcp.browse.server import browse_mcp
from ebay_mcp.taxonomy.server import taxonomy_mcp
from ebay_mcp.inventory.server import inventory_mcp
from ebay_mcp.prompts.server import prompts_mcp

# Create the main MCP server
instruction_text = """This MCP server provides tools to interact with various eBay APIs.

PRIMARY WORKFLOW:
1. Create Inventory Item (inventoryAPI_manage_inventory_item::create)
2. Create Offer (inventoryAPI_manage_offer::create) 
3. Publish Offer (inventoryAPI_manage_offer::publish)

AVAILABLE OPERATIONS:
• Inventory Items: CREATE, GET, MODIFY, DELETE
• Offers: CREATE, GET, MODIFY, PUBLISH, WITHDRAW

KEY CONCEPTS:
• One-to-One Relationship: 1 Inventory Item maps to 1 Offer
• Inheritance: Offers inherit the Inventory Item Description (no separate Offer Description needed)
• Modification Rule: Modify Item/Offer attributes at the level where they were created
• Minimum Fields: Only minimum required fields are necessary

CATEGORY & ASPECTS:
• Use 'Get Category Suggestions' to find appropriate categories
• Use 'Get Aspects for Category' to get required/recommended item attributes

WORKFLOW FLEXIBILITY:
While the primary workflow above is typical, you can use inventoryAPI_manage_inventory_item and inventoryAPI_manage_offer tools independently to GET, MODIFY, or DELETE existing items and WITHDRAW offers as needed."""

mcp = FastMCP(
    name="eBay API",
    instructions=instruction_text
)

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

    # Mount custom prompts server
    mcp.mount("customPrompts", prompts_mcp)
    logger.info("Mounted custom prompts MCP server")
    
    # Test and database tools have been removed as they are no longer needed
    
    logger.info("All sub-servers mounted successfully")

# Mount all servers
mount_servers()

# When running this file directly, start the MCP server
if __name__ == "__main__":
    logger.info("Starting FastMCP server with stdio transport...")
    logger.info("Server is configured with dynamically mounted sub-servers")
    mcp.run()
