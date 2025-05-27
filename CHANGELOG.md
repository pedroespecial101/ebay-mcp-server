## Updates in TrajectoryID fix_server_startup_config (0019), 27052025 - 21:05.00

- Switched to using stdio transport for FastMCP server as it's the only supported transport
- Simplified server startup script to focus on stdio transport
- Updated documentation to clarify that an MCP client should be used to interact with the server

## Updates in TrajectoryID add_server_startup_message (0018), 27052025 - 21:00.00

- Added a main block to `src/server.py` to properly start the FastMCP server
- Added startup messages with instructions for testing the authentication endpoint

## Updates in TrajectoryID add_test_auth_endpoint (0017), 27052025 - 20:57.00

- Added a new `test_auth()` endpoint to `src/server.py` to verify token retrieval
- The endpoint returns the first 50 characters of the token and its length for verification

## Updates in TrajectoryID enhance_offer_debugging (0016), 27052025 - 20:55.00

- Enhanced `get_offer_by_sku` function in `src/server.py` with:
  - Added detailed debug logging for each API request and response
  - Improved error handling with more descriptive messages
  - Added response header logging for better diagnostics
  - Added handling for empty offer lists
  - Improved status code and response body logging

## Updates in TrajectoryID fix_server_startup (0015), 27052025 - 20:53.00

- Fixed server startup in `start.sh` by removing the `-m fastmcp run` parameter which was causing the server to fail to start.
- The server now starts directly with the Python script path.

## Updates in TrajectoryID enhance_offer_lookup (0014), 27052025 - 20:50.00

- Enhanced `get_offer_by_sku` function in `src/server.py` with:
  - Added marketplace ID and end user context headers
  - Implemented fallback mechanism to find offer by SKU and then by offer ID
  - Added debug logging for troubleshooting
  - Improved error handling and response messages

## Updates in TrajectoryID add_oauth_token_support (0013), 27052025 - 20:45.00

- Updated `ebay_service.py` to support direct OAuth token usage from `EBAY_OAUTH_TOKEN` environment variable.
- Added fallback to client credentials flow when OAuth token is not provided.

## Updates in TrajectoryID update_ebay_scopes (0012), 27052025 - 20:40.00

- Updated `ebay_service.py` to include all necessary eBay API OAuth scopes with detailed comments.
- Added scopes for marketing, inventory, account management, fulfillment, analytics, finances, payment disputes, identity, reputation, notifications, stores, and eDelivery.

## Updates in TrajectoryID add_server_management_script (0011), 27052025 - 20:19.00

- Added `start.sh` script for easy server management (start, stop, restart, status).
- Script automatically handles PID management and logging.
- Made script executable with `chmod +x`.

## Updates in TrajectoryID add_offer_by_sku_tool (0010), 27052025 - 20:17.00

- Added `get_offer_by_sku` tool to `src/server.py` for fetching offer details from eBay Sell Inventory API.

## Updates in TrajectoryID add_item_aspects_tool (0009), 27052025 - 20:13.00

- Added `get_item_aspects_for_category` tool to `src/server.py` for fetching item aspects from eBay Taxonomy API.

## Updates in TrajectoryID add_category_suggestions_tool (0008), 27052025 - 17:18.00

- Added `get_category_suggestions` tool to `src/server.py` for eBay Taxonomy API integration.

## Updates in TrajectoryID mcp_config_manual_entry (0007), 27052025 - 17:14.00

- Manually added `Ebay API` server entry to `~/.codeium/windsurf/mcp_config.json`.

## Updates in TrajectoryID cleanup_debug_prints (0006), 27052025 - 17:06.00

- Removed debug print statements from `src/ebay_service.py`.

## Updates in TrajectoryID debug_env_load (0005), 27052025 - 17:05.00

- Added debug print statements to `src/ebay_service.py` to diagnose `.env` loading issues.

## Updates in TrajectoryID explicit_env_load (0004), 27052025 - 17:03.00

- Modified `src/ebay_service.py` to explicitly load `.env` from the project root.

## Updates in TrajectoryID env_load_fix (0003), 27052025 - 17:01.00

- Added `load_dotenv()` to `src/ebay_service.py` to ensure environment variables are loaded correctly.

## Updates in TrajectoryID server_setup (0002), 27052025 - 16:57.00

- Created Python venv and installed dependencies in `.venv`.
- Started FastMCP server via CLI.

## Updates in TrajectoryID requirements_setup (0001), 27052025 - 16:54.09

- Created `requirements.txt` with project dependencies.
