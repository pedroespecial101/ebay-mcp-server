## Updates in TrajectoryID <align_oauth_callback_and_token_redirect_uri (ebay_mcp_server)>, <29052025 - 08:30.00>

- Modified `ebay_auth/ebay_auth.py` to correctly handle OAuth redirection in environments using a public-facing URL (e.g., via Cloudflare tunnel):
    - Changed `LOCAL_CALLBACK_PATH` from `"/ebay_auth_callback"` to `"/oauth/callback"` to align with common existing setups and the previous `ebay_authentication_token.py` script. This ensures the local Python HTTP server listens on the expected path.
    - Updated the `_exchange_auth_code_and_get_user_details` function:
        - The `redirect_uri` parameter in the token exchange POST request is now sourced from a new environment variable: `EBAY_APP_CONFIGURED_REDIRECT_URI`.
        - This new variable must be set in the `.env` file to the exact public redirect URI that eBay sends the user back to (e.g., `https://your-public-domain.com/oauth/callback`). This is crucial for the token exchange to succeed when not operating purely on `localhost`.
    - The initial authorization request to eBay (in `initiate_user_login`) correctly continues to use the `EBAY_RU_NAME` as its `redirect_uri` parameter.

## Updates in TrajectoryID <debug_invalid_scope_reduce_scopes (ebay_mcp_server)>, <29052025 - 08:16.00>

- Further debugged `invalid_scope` error in `ebay_auth/ebay_auth.py` by reducing `DEFAULT_SCOPES` to a single, common scope: `"https://api.ebay.com/oauth/api_scope/commerce.identity.readonly"`. This is to isolate whether the issue is with a specific scope or a more general configuration problem.

## Updates in TrajectoryID <fix_invalid_scope_ebay_auth (ebay_mcp_server)>, <29052025 - 08:14.00>

- Corrected an `invalid_scope` error in `ebay_auth/ebay_auth.py` by removing the overly general scope `"https://api.ebay.com/oauth/api_scope "` from the `DEFAULT_SCOPES` list. This scope was likely causing the OAuth flow to fail.

## Updates in TrajectoryID <update_ebay_auth_port (ebay_mcp_server)>, <29052025 - 08:12.00>

- Modified `ebay_auth/ebay_auth.py` to change the `LOCAL_SERVER_PORT` for the OAuth callback handler from `8000` to `9292`. This aligns with the port used in the older `ebay_authentication_token.py` script.

## Updates in TrajectoryID <Add eBay OAuth login flow to ebay_auth.py, (add_ebay_login_flow_to_auth_module)>, <29052025 - 08:03.00>

- Modified `ebay_auth/ebay_auth.py` to include a full OAuth2 user login flow:
    - Added new imports: `webbrowser`, `threading`, `http.server`, `socketserver`, `queue`, `urllib.parse`, `uuid`.
    - Defined new constants for eBay authorization endpoint, default OAuth scopes, local HTTP server port, and callback path.
    - Integrated an `OAuthCallbackHandler` class (adapted from `ebay_authentication_token.py`) to handle the redirect from eBay after user authorization.
    - Added a function `_start_local_http_server` to run the callback server in a separate thread.
    - Created `_exchange_auth_code_and_get_user_details` to handle the exchange of the authorization code for access and refresh tokens, and then fetch user details using the new tokens. This function saves the tokens and user details to the `.env` file.
    - Implemented the main new public function `initiate_user_login()` which:
        - Constructs the eBay authorization URL.
        - Opens the URL in the user's web browser.
        - Starts the local HTTP server.
        - Waits for the authorization code (or error) from the callback handler via a queue.
        - Calls `_exchange_auth_code_and_get_user_details` upon receiving the code.
        - Logs the outcome.
    - Updated the command-line interface to include a new `login` action that triggers `initiate_user_login()`.
    - Refined `refresh_access_token` to include scopes in the refresh request, as recommended by eBay.
    - Improved `get_user_details` to avoid potential recursive loops during token refresh attempts.
    - Ensured `_save_to_env` converts values to strings before saving.
    - Added basic CSRF protection using a `state` parameter (validation part is noted as a TODO).

## Updates in TrajectoryID <use_fastmcp_dev_in_start_sh (ebay_mcp_server)>, 29052025 - 07:30.58

- Modified `start.sh` to use `fastmcp dev src/server.py` for starting the server.
- This change is based on FastMCP documentation, which suggests `fastmcp dev` for testing servers over STDIO and launching an MCP Inspector.
- This might provide the necessary environment or active STDIO channel to prevent the server from exiting prematurely.
- Updated the `pkill` command in `start.sh` to `pkill -f "fastmcp dev $SERVER_SCRIPT"` to correctly stop server instances started with the new command.

## Updates in TrajectoryID <use_fastmcp_run_in_start_sh (ebay_mcp_server)>, 29052025 - 07:30.13

- Modified `start.sh` to use `fastmcp run src/server.py --transport stdio` for starting the server, instead of `python src/server.py`.
- This change aligns with FastMCP's recommended way of running servers via its CLI, which might handle event loops or server context differently.
- Updated the `pkill` command in `start.sh` to `pkill -f "fastmcp run $SERVER_SCRIPT"` to correctly stop server instances started with the new command.

## Updates in TrajectoryID <fix_mcp_run_call_transport (ebay_mcp_server)>, 29052025 - 07:28.09

- Corrected the `mcp.run()` call in `src/server.py` to use the correct `transport="stdio"` argument.
- Previously, `mcp.run()` was incorrectly called with a list of server instances (`mcp_server_list`) instead of the transport string, causing a `ValueError: Unknown transport`.
- Removed the unused `mcp_server_list` variable.

## Updates in TrajectoryID <add_mcp_run_debug_logging (ebay_mcp_server)>, 29052025 - 07:26.18

- Added debug logging around the `mcp.run()` call in `src/server.py` to help diagnose server startup issues.
- Logged messages "Attempting to call mcp.run()..." and "mcp.run() completed or exited." are now emitted before and after the `mcp.run()` execution respectively.
- Ensured `mcp.run()` is called with `mcp_server_list`.

## Updates in TrajectoryID <improve_start_sh_error_detection (ebay_mcp_server)>, 29052025 - 07:25.22

- Modified `start.sh` to improve error detection during server startup.
- Added a command to clear `fastmcp_server.log` (`echo "Clearing $LOG_FILE for fresh start..." > "$LOG_FILE"`) before the `python src/server.py` execution.
- This ensures that the script's `grep` command for error checking operates on a clean log file for each startup attempt, preventing old errors from causing false positives.

## Updates in TrajectoryID <fix_ebay_auth_nameerror (ebay_mcp_server)>, 29052025 - 07:23.36

- Fixed a `NameError: name 'args' is not defined` in `ebay_auth/ebay_auth.py`.
- The `elif args.action == "refresh_token":` block was incorrectly indented, causing it to be outside the `if __name__ == "__main__":` guard.
- Corrected the indentation to ensure command-line argument parsing logic only runs when the script is executed directly, not when imported as a module.

## Updates in TrajectoryID <integrate_ebay_auth_module_server_py_updates (ebay_mcp_server)>, 29052025 - 07:21.53

- Refactored `src/server.py` to integrate robust eBay API token refresh mechanism:
    - Added new helper function `_execute_ebay_api_call` to centralize API call logic, including:
        - Initial token acquisition.
        - Execution of specific API call logic for each tool.
        - Handling of 401 (Unauthorized) errors by attempting token refresh using `ebay_auth.ebay_auth.refresh_access_token`.
        - Retrying the API call with the new token if refresh is successful.
        - Comprehensive logging for all stages of the process.
    - Updated `is_token_error` to include new error messages from `ebay_service.py`.
    - Modified MCP tools (`search_ebay_items`, `get_category_suggestions`, `get_item_aspects_for_category`, `get_offer_by_sku`) to:
        - Define an inner `_api_call` function for their specific request logic.
        - Utilize the new `_execute_ebay_api_call` helper function for all eBay API interactions.
        - Ensure `response.raise_for_status()` is used to propagate HTTP errors for handling by the helper.
- Added `asyncio` and `ebay_auth.ebay_auth.refresh_access_token` imports to `src/server.py`.

## Updates in TrajectoryID <integrate_ebay_auth_module (ebay_mcp_server)>, 29052025 - 07:26.30

- Created a new Python module `ebay_auth` in the `ebay_auth/` directory to handle eBay API authentication and token management.
- The module `ebay_auth/ebay_auth.py` includes:
    - Functions to load eBay API credentials and tokens from a `.env` file.
    - `refresh_access_token()`: Refreshes the eBay access token using the stored refresh token and saves the new token(s) to `.env`.
    - `get_user_details()`: Fetches the eBay User ID and User Name using an access token (refreshes token if necessary) and saves details to `.env`.
    - Command-line interface to manually trigger `get_user` or `refresh_token` actions.
    - Logging to trace token usage and assist in debugging.
- Added `ebay_auth/requirements.txt` specifying dependencies (`python-dotenv`, `requests`).
- Added `ebay_auth/__init__.py` to make the directory a Python package.

## Updates in TrajectoryID <Removed redundant dotenv dependency from requirements.txt>, 28052025 - 18:05:30

- Removed `dotenv>=0.9.9` from `requirements.txt` to rely solely on `python-dotenv==1.0.0`, preventing potential conflicts and cleaning up dependencies.

## Updates in TrajectoryID implement_daily_log_rotation (0022), 28052025 - 09:05.00

- Implemented daily log rotation using `TimedRotatingFileHandler` in `src/server.py`.
- Centralized logging configuration in `src/server.py` and removed `logging.basicConfig()` from `src/ebay_service.py`.
- Modified `start.sh` to append (`>>`) to log files instead of truncating (`>`), complementing the new Python-based log rotation.

## Updates in TrajectoryID simplify_start_script (0020), 28052025 - 08:18.00

- Simplified `start.sh` script:
  - Removed `start`, `stop`, `restart`, `status` command arguments and associated functions.
  - The script now unconditionally kills any existing server instances matching `python src/server.py` using `pkill -f` before starting a new one.
  - Removed PID file (`fastmcp_server.pid`) creation and management.
  - Updated log file path to `logs/fastmcp_server.log` and added creation of the `logs` directory if it doesn't exist.
  - Added a check after server startup to confirm if the process is running and provide feedback, including tailing the log on failure.

## Updates in TrajectoryID brain_dump_issue_resolution_and_logging_improvements (2025-05-28T07:37:35+01:00), 28052025 - 07:50.00

- **Logging Overhaul**:
    - Implemented Python's `logging` module for robust server logging in `src/ebay_service.py` and `src/server.py`.
    - Logs are now directed to `logs/fastmcp_server.log`.
    - Log files are appended, preventing loss of history on restart.
    - Implemented daily log rotation, keeping the last 7 days of logs.
    - Replaced all `print()` statements with structured `logger` calls (info, debug, error).
- **eBay Authentication Enhancements**:
    - Introduced `USE_ENV_OAUTH_TOKEN` environment variable in `.env` to switch between using a hardcoded `EBAY_OAUTH_TOKEN` (if `True`) and the client credentials flow (if `False` or unset - default).
    - Added detailed logging for token acquisition, indicating which method (environment token or client credentials) is used.
    - Corrected client credentials flow in `src/ebay_service.py` to use `EBAY_CLIENT_ID` and `EBAY_CLIENT_SECRET` for `httpx.BasicAuth`.
    - Improved error handling in MCP tools: if token acquisition fails, the specific error is logged and returned to the MCP client, preventing API calls with invalid tokens.
    - Refined OAuth scopes requested during client credentials flow to be more minimal and primarily ReadOnly, while retaining `https://api.ebay.com/oauth/api_scope/sell.inventory` for `get_offer_by_sku` functionality.
- **Debugging Improvements**:
    - Added extensive debug logging to the `get_offer_by_sku` MCP tool in `src/server.py`, including details of request headers, parameters, and API responses to help diagnose issues like the 401 error.

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

## Updates in TrajectoryID enhance_oauth_userid_and_lint_fixes, <28052025 - 20:33.12>

- **Enhanced eBay OAuth Flow (`ebay_authentication_token.py`)**:
    - Modified the OAuth callback handler to fetch and display the eBay UserID on the HTML redirect page after successful authentication.
    - Refactored the token exchange and user information fetching logic into a new helper function `_exchange_code_and_get_user()`.
    - The local HTTP server now shows a page like: "Authentication Successful! Logged in as eBay UserID: [actual_user_id]".
    - Error messages on the HTML redirect page are also more detailed.
    - Ensured that both `access_token` and `refresh_token` (if provided) are saved to the `.env` file, along with the `EBAY_OAUTH_TOKEN` and `EBAY_OAUTH_REFRESH_TOKEN` respectively.
    - Improved robustness of `.env` file path detection for loading and saving credentials.
    - Added `find_dotenv` to imports in `ebay_authentication_token.py`.
    - Corrected linting errors at the end of the `main` function by removing orphaned `try-except` remnants and ensuring proper use of `sys.exit()`.

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

## Updates in TrajectoryID diagnostic_logging (0021), 28052025 - 08:53.00

- Added diagnostic logging to `src/ebay_service.py` and `src/server.py` to display the prefix of the OAuth token being used. This is to help differentiate which token is active when `USE_ENV_OAUTH_TOKEN` is true, especially when comparing behavior between direct script execution (like `test_offer.py`) and execution within the MCP server environment.
