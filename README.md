# eBay MCP Server

For new second-hand listings, use the `research_*`, `media_*`, and `listing_*`
tools as one combined endpoint. Research tools provide read-only ebay.co.uk live
listing research; media and listing tools provide private image staging,
validation, resumable creation, fee approval, publication verification, and
conservative draft cleanup. The low-level inventory and offer tools remain
available for diagnostics.

For listings started with **Sell one like this** in the eBay app, use the narrow
`trading_*` tools. Publish a truthful quantity-one fixed-price placeholder first,
then call `trading_get_recent_seller_listings`, inspect it with
`trading_get_item`, view its photographs with `trading_view_item_images`, present
the proposed diff to the seller, and only then call
`trading_revise_fixed_price_item` with the returned revision token. App/Seller
Hub drafts and scheduled listings are not supported by this workflow.

## Overview

This project implements a Model Context Protocol (MCP) server for eBay UK
research and seller workflows. The server uses FastMCP to expose eBay API
endpoints as callable functions that can be accessed by AI assistants and other
MCP clients.

It now vendors the read-only UK Browse research surface from
`/Users/petetreadaway/Documents/ebay.co.uk_Browse_MCP` under the `research_*`
namespace. The research client uses application credentials only and deliberately
ignores seller OAuth values. Seller, inventory, listing, media, and Trading tools
continue to use user-level seller auth where required.

Additionally, you can test MCP tools using **MCP Inspector** — an open-source browser interface available at <https://github.com/modelcontextprotocol/inspector>.

## Key Features

- OAuth2 authentication with eBay's API using user-level tokens
- Token management system with automatic refresh capabilities
- Multiple MCP functions for interacting with eBay APIs:
  - Read-only UK Browse research for live listing search, item details, and image similarity
  - Legacy Browse API helper tools for compatibility
  - Taxonomy API for category suggestions and item aspects
  - Inventory API for comprehensive inventory management:
    - Retrieve inventory items by SKU or with pagination
    - Retrieve offer details by SKU
    - Update offers, withdraw offers, get listing fees
    - Delete inventory items
- Pydantic models for request/response validation and type safety
- Robust error handling and token refresh logic
- Centralized logging system with timed rotation
- Server management script for easy lifecycle management

## Technology Stack

- **FastMCP**: Framework for building Model Context Protocol servers
- **Python 3**: Core programming language
- **eBay REST APIs**: Various endpoints for eBay platform integration
- **OAuth2**: Authentication mechanism for eBay API access
- **python-dotenv**: Environment variable management
- **httpx**: Asynchronous HTTP client for API calls
- **logging**: Standard Python logging with TimedRotatingFileHandler
- **Pydantic**: Data validation and type safety throughout the codebase (MCP tools)

## Project Structure

```
ebay-mcp-server/
├── .env.example            # Documented configuration keys (no secrets)
├── CHANGELOG.md            # Documentation of changes to the project
├── README.md               # Project documentation (this file)
├── ebay_auth/              # eBay authentication module
│   ├── __init__.py         # Package initialization
│   ├── ebay_auth.py        # OAuth implementation for eBay
│   └── requirements.txt    # Auth module specific dependencies
├── ebay_docs/              # eBay API documentation and project reference files
├── logs/                   # Server logs directory
│   └── fastmcp_server.log  # Server log file with rotation
├── start_mcp_inspector.sh  # Script to start MCP Inspector locally
├── start_mcp_server_instance.sh # MCP server management script for local testing
├── requirements.txt        # Python dependencies
├── src/                    # Source code directory
│   ├── ebay_mcp/           # Modular MCP servers for eBay APIs
│   │   ├── auth/           # Authentication API server
│   │   │   └── server.py   # Auth MCP tools implementation
│   │   ├── browse/         # Browse API server
│   │   │   └── server.py   # Browse MCP tools implementation
│   │   ├── inventory/      # Inventory API server
│   │   │   ├── server.py   # Inventory MCP base implementation
│   │   │   ├── manage_inventory_item.py # Inventory item create, modify, get, delete
│   │   │   └── manage_offer.py  # Offer create, modify, withdraw, publish, get
│   │   ├── catalog/         # Catalog API server and GTIN search tool
│   │   └── taxonomy/       # Taxonomy API server
│   │       └── server.py   # Taxonomy MCP tools implementation
│   ├── utils/              # Shared utility modules
│   │   └── api_utils.py    # Shared API utility functions
│   ├── ebay_service.py     # eBay service utilities
│   ├── main_server.py      # Main MCP server that mounts all sub-servers
│   └── models/             # Pydantic models for data validation
│       ├── __init__.py     # Package initialization
│       ├── ebay/           # eBay API specific models
│       │   ├── __init__.py # Package initialization
│       │   ├── inventory.py # Inventory API models
│       │   └── taxonomy.py # Taxonomy API models
│       └── mcp_tools.py    # MCP tool parameter models
└── tests/                  # Test directory for unit tests
```

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd ebay-mcp-server
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Use Doppler `ebay-mcp/dev` for the normal local installation. See `.env.example` for every supported key.

5. Run the combined server with Doppler injection:

   ```bash
   doppler run --project ebay-mcp --config dev -- ./start_mcp_server_instance.sh
   ```

For a local-file fallback, create a gitignored `.env` from `.env.example`, or set `EBAY_CREDENTIALS_FILE` to an absolute dotenv path. The OAuth flow reads and writes that file when `EBAY_TOKEN_STORE` is not `doppler`.

## Doppler-backed local setup

For day-to-day use, keep the seller secrets in Doppler and run the server locally
through `doppler run`. The same server can run as stdio or Streamable HTTP.

Configured secret names:

- `EBAY_CLIENT_ID`
- `EBAY_CLIENT_SECRET`
- `EBAY_RU_NAME`
- `EBAY_APP_CONFIGURED_REDIRECT_URI`
- `EBAY_USER_REFRESH_TOKEN`
- `EBAY_PAYMENT_POLICY_ID`
- `EBAY_RETURN_POLICY_ID`
- `EBAY_FULFILLMENT_POLICY_ID`
- `EBAY_MERCHANT_LOCATION_KEY`
- `EBAY_MARKETPLACE_ID`
- `EBAY_LOCALE`
- `EBAY_CURRENCY`
- `EBAY_DELIVERY_COUNTRY`

The app client ID and secret are shared by `research_*` and seller flows. Seller
refresh auth remains seller-only. `EBAY_USER_ACCESS_TOKEN` is deliberately not
stored in Doppler: the server mints it from the refresh token at startup and
keeps it in process memory.

Launch:

```bash
doppler run --project ebay-mcp --config dev -- ./start_mcp_server_instance.sh
```

Streamable HTTP with tailnet HTTPS for local testing:

```bash
doppler run --project ebay-mcp --config dev -- ./scripts/start_tailnet_https.sh
```

The Python server listens on `http://127.0.0.1:8766/mcp`; when
`EBAY_MCP_ENABLE_TAILSCALE_SERVE=1` the script asks Tailscale Serve to publish
that local HTTP server as tailnet-only HTTPS.

For a fresh seller login, run:

```bash
doppler run --project ebay-mcp --config dev -- \
  python ebay_auth/ebay_auth.py login
```

With `EBAY_TOKEN_STORE=doppler`, new or rotated refresh tokens are written back to `ebay-mcp/dev`. Access tokens are not persisted.

Set `CLEAR_EBAY_USER_TOKENS=1` only when you deliberately want to clear local user tokens before starting.

## ChatGPT boundary

The broad seller MCP is no longer a ChatGPT App. Its legacy
`ebay-seller-chatgpt` tunnel profile is retained only as rollback history and
must remain stopped/unlinked. ChatGPT uses the dedicated, narrow eBay Listing
Studio App instead; Listing Studio calls this seller MCP internally over
loopback. Seller OAuth remains local and seller credentials remain in
Doppler `ebay-mcp/dev`.

## Usage

### Server Management

#### Local Development and Testing

The `start_mcp_server_instance.sh` script is provided for local development and testing purposes. It is **not** used by the IDE's MCP integration:

```bash
# Start the server for local testing
./start_mcp_server_instance.sh

# Check logs
tail -f logs/fastmcp_server.log
```

**Important Note:** Running the `start_mcp_server_instance.sh` script does not affect the IDE's MCP integration, which runs in a separate process managed by the IDE's configuration. These are two completely separate instances of the server.

#### IDE MCP Integration

For AI assistants and IDEs that support the Model Context Protocol (MCP), the server is typically configured in the IDE's MCP configuration file. A sample configuration might look like this:

```json
"ebay_seller": {
  "command": "doppler",
  "args": [
    "run", "--project", "ebay-mcp", "--config", "dev", "--",
    "/path/to/ebay-mcp-server/.venv/bin/python",
    "/path/to/ebay-mcp-server/src/main_server.py"
  ],
  "env": {}
}
```

This configuration tells the IDE to:
1. Inject seller configuration from Doppler `ebay-mcp/dev`
2. Run the seller server with its own virtual environment
3. Keep it registered separately from `ebay_uk_browse`

**Important Notes:** 
- Changes to the MCP server **code** will require restarting the MCP server process in your IDE for changes to take effect, which is separate from running the `start_mcp_server_instance.sh` script.
- Authentication through `trigger_ebay_login` updates the current process and durable refresh-token store without requiring a restart.
- When using Doppler, prefer `doppler run --project ebay-mcp --config dev -- ./start_mcp_server_instance.sh` instead of exporting secrets manually.

### MCP Client Integration

The server implements the Model Context Protocol, allowing AI assistants and other MCP clients to call the exposed functions directly. Available functions include:

### Authentication & Testing Tools
- `test_auth()`: Test authentication and token retrieval
- `trigger_ebay_login()`: Initiates the eBay OAuth2 login flow directly from the MCP IDE

### Preferred Read-Only Research Tools
- `research_search_items`: live keyword/GTIN search with category, price, condition, buying-option, location, aspect, fitment, refinement, sort, and pagination inputs.
- `research_get_item`: compact details for a live Browse API item ID.
- `research_search_by_image`: UK-supported visual-similarity search from a public HTTPS image URL.
- `research_search_by_staged_image`: visual-similarity search from a trusted
  private `r2:` staging reference; the source image is sent directly to eBay and
  is never made public.

Research prices are current asking prices or auction bids, not completed-sale
comparables.

### Legacy Browse API Tools
- `browseAPI_search_ebay_items(query: str, limit: int = 10)`: simple live item search.
- `browseAPI_search_by_image`: visual-similarity search kept for compatibility.

### Taxonomy API Tools
- `get_category_suggestions(query: str)`: Get category suggestions from eBay Taxonomy API
- `get_item_aspects_for_category(category_id: str)`: Get item aspects for a specific category

### Inventory API Tools
- `manage_inventory_item(sku: str, action: str, item_data: Optional[dict])`: Manages eBay inventory items. Actions include 'create', 'modify', 'get', 'delete'. For 'create' and 'modify', the `item_data` payload follows a limited-field schema (title, description, identifiers, condition, availability) as defined by the InventoryItemDataForManage model.
- `manage_offer(sku: str, action: str, offer_data: Optional[dict])`: Manages eBay offers. Actions include 'create', 'modify', 'withdraw', 'publish', 'get'. The `offer_data` parameter is a complex object required for 'create' and 'modify' actions; refer to the tool's auto-generated schema for detailed field names (using `camelCase`) and descriptions.

### Catalog API Tools
- `search_by_gtin(gtin: str)`: Search the UK eBay catalog for a product by EAN, ISBN, UPC, or other GTIN.

### Narrow Trading API Tools

- `trading_get_recent_seller_listings`: Find recent active UK quantity-one fixed-price listings suitable for takeover.
- `trading_get_item`: Return the complete editable state and optimistic-concurrency revision token.
- `trading_view_item_images`: Return actual seller-listing photographs as
  normalized model-vision image blocks. It defaults to one image and returns at
  most three per call; follow `has_more` and `next_start_index` to review the
  complete ordered photo set.
- `trading_revise_fixed_price_item`: Apply an explicitly confirmed essentials-only patch, then read the listing back.
- `trading_upload_listing_pictures`: Move privately staged images to EPS using the Media API.
- `trading_verify_add_fixed_price_item`: Validate a direct Trading proposal and
  return fees, warnings, errors and a short-lived token.
- `trading_add_fixed_price_item`: Re-verify and immediately publish an unchanged proposal within an explicit fee ceiling.

Direct Trading adds use the existing payment, return, fulfilment, and merchant
location settings. Proposals may include a seller SKU with SKU inventory
tracking plus metric packed weight, dimensions, and package type.
`EBAY_ITEM_LOCATION` and `EBAY_ITEM_POSTAL_CODE` can override the city/postcode
resolved from that merchant location. They create no Inventory API item or
Offer. `UploadSiteHostedPictures` is deliberately
not implemented because eBay is decommissioning it; image uploads use the Media
API replacement.

Local media staging accepts the existing `EBAY_IMAGE_IMPORT_DIR` plus the
separate `EBAY_LISTING_STUDIO_IMPORT_DIR`, which defaults to Listing Studio's
`~/Library/Application Support/eBay Listing Studio/images/ebay` derivative
directory. Additional approved roots may be supplied with the path-separated
`EBAY_IMAGE_IMPORT_DIRS`; path traversal remains rejected.

Trading calls automatically refresh an expired seller access token once and
retry the original request. `browseAPI_search_by_image` is a visual similarity
search for finding other live listings; it does not display an item's source
photographs to the model.

For visual inspection from a known eBay CDN image URL, use
`media_view_ebay_image`. It accepts approved eBay image hosts only, fetches one
image, strips metadata, resizes it to a safe bound, re-encodes it as JPEG, and
does not return the source URL. This is separate from `media_stage_images`,
which stages photographs for listing creation but deliberately keeps image
bytes out of the model context.

### Safe validation

Run focused unit and MCP-discovery checks before any seller mutation. The older inventory and offer integration tests can create, publish, withdraw, or delete real account data and must not be run as a generic smoke suite.

```bash
.venv/bin/python -m pytest tests/test_credentials_and_defaults.py
doppler run --project ebay-mcp --config dev -- \
  .venv/bin/python scripts/smoke_mcp_discovery.py
doppler run --project ebay-mcp --config dev -- \
  .venv/bin/python scripts/live_read_smoke.py
```

## Adding New Functions

This project uses a **modular tool implementation pattern** for organizing MCP tools. Each tool is implemented in its own file and then registered with the appropriate MCP server.

### Modular Tool Pattern

For complex APIs like eBay Inventory, tools are organized as follows:

1. **Individual Tool Files**: Each MCP tool is implemented in its own file
2. **Server Registration**: Tools are imported and registered in the main server file (e.g., `inventory/server.py`)
3. **Shared Utilities**: Common functionality like authentication is handled by shared utilities (`execute_ebay_api_call`)

### Adding a New Tool

To add a new function to the MCP server, follow these steps:

1. **Identify the eBay API endpoint** you want to expose
2. **Create appropriate Pydantic models** in `src/models/` for request parameters and responses
3. **Choose the implementation approach**:
   - For simple tools: Add directly to the main server file
   - For complex APIs: Create a separate tool file in the appropriate subdirectory
4. **Implement the function logic** using the `execute_ebay_api_call` helper for consistent error handling
5. **Follow the existing pattern** for API calls with Pydantic validation:

```python
@mcp.tool()
async def your_new_function(param1: str, param2: int = 10) -> str:
    """Your function description"""
    # Validate parameters using Pydantic model
    params = YourFunctionParams(param1=param1, param2=param2)
    logger.info(f"Executing your_new_function with params: {params.model_dump()}")

    async def _api_call(access_token: str, client: httpx.AsyncClient):
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        # Use model_dump to convert Pydantic model to dict
        payload = params.model_dump(exclude_none=True)
        url = "https://api.ebay.com/path/to/endpoint"
        
        response = await client.get(url, headers=headers, params=payload)
        response.raise_for_status()
        return response.text

    async with httpx.AsyncClient() as client:
        result = await _execute_ebay_api_call("your_new_function", client, _api_call)
        
        # Parse and return response using Pydantic model
        if not result.startswith('Token acquisition failed'):
            try:
                result_json = json.loads(result)
                response_model = YourFunctionResponse(**result_json)
                # You can perform additional transformations here
            except Exception as e:
                logger.error(f"Error parsing response: {e}")
                
        return result
```

6. Restart the server using `./start_mcp_server_instance.sh` to make the new function available

## Pydantic Integration

This project uses Pydantic extensively for data validation, serialization, and documentation of both requests and responses.

### Model Organization

Pydantic models are organized in the following structure:

- `src/models/mcp_tools.py`: Contains parameter models for MCP tools
- `src/models/ebay/inventory.py`: Models for eBay Inventory API
- `src/models/ebay/taxonomy.py`: Models for eBay Taxonomy API

### Parameter Validation

All MCP tools use Pydantic models for parameter validation before making API calls. This ensures:

1. Required parameters are provided
2. Parameters have the correct types
3. Parameters meet any additional constraints (min/max values, patterns, etc.)

Example parameter model:

```python
class ItemAspectsParams(EbayBaseModel):
    """Parameters for the get_item_aspects_for_category tool."""
    
    category_id: str = Field(..., description="The category ID to get aspects for.")
    
    @field_validator("category_id")
    @classmethod
    def validate_category_id(cls, value):
        """Ensure category_id is a string, even if a numeric value is provided."""
        if value is not None and not isinstance(value, str):
            return str(value)
        return value
```

### Response Parsing

API responses are parsed into Pydantic models for type safety and easy data access. This allows:

1. Validation of API responses
2. Structured access to response data
3. Automatic conversion between JSON and Python objects

Example response model:

```python
class ToolResponse(EbayResponse[dict]):
    """Structured response returned by an eBay MCP tool."""

    status_code: int
    details: dict | None = None
```

## Authentication Flow

The project implements the OAuth2 authorization code flow for eBay with two authentication methods:

### Method 1: Command-line Authentication

1. User initiates login via the `ebay_auth.py` script:
   ```bash
   python ebay_auth/ebay_auth.py login
   ```
2. Browser opens to eBay login page
3. After login, eBay redirects to the configured redirect URI
4. The script exchanges the authorization code for access and refresh tokens
5. The refresh token is saved to Doppler (or the configured dotenv fallback)
6. The access token remains in process memory for API calls

### Method 2: In-IDE MCP Authentication (Recommended)

1. AI assistant or user calls the `trigger_ebay_login` MCP tool
2. Browser opens to eBay login page
3. After login, eBay redirects to the configured redirect URI
4. Durable refresh auth is saved to Doppler or the configured dotenv fallback
5. The MCP server immediately begins using the new tokens without requiring a restart

In both cases, when the access token expires, it automatically refreshes using the refresh token. If the refresh token also expires or becomes invalid, the system will prompt for re-authentication using the `trigger_ebay_login` tool.

## Tool Testing (MCP Inspector)

To interactively explore and execute MCP tools in your browser, use [MCP Inspector](https://github.com/modelcontextprotocol/inspector):

1. Ensure the Doppler CLI can access `ebay-mcp/dev`.
2. Start MCP Inspector with the provided script; its config launches the seller server:
   ```bash
   ./start_mcp_inspector.sh
   ```
3. Open the printed URL in your browser and point the Inspector at your local MCP server endpoint.

## Future Plans

Potential enhancements for the project:

1. **Multiple User Support**: Allow the server to manage tokens for multiple eBay seller accounts
2. **More eBay APIs**: Expand the available functions to cover additional eBay APIs
3. **Expanded MCP Inspector**: Add more features to the testing interface
4. **Automated Test Suite**: Develop comprehensive tests for all components
   - Order Management API
   - Fulfillment API
   - Marketing API
   - Compliance API
5. **Rate Limiting**: Implement rate limiting to comply with eBay API usage policies
6. **Web Interface**: Add a web dashboard for monitoring the server status and token management
7. **Webhook Support**: Enable webhooks for eBay notifications
8. **OCI Packaging**: Add a tailnet-only container deployment using the same Doppler keys

## Security Considerations

- Doppler `ebay-mcp/dev` is the source of truth for production eBay credentials and seller refresh auth
- The local `.env` remains a gitignored fallback and legacy source for the shared Browse app keyset
- Never log or return client secrets, authorization codes, access tokens, or refresh tokens
- Regularly rotate eBay API credentials according to security best practices
- Use HTTPS for all redirect URIs in production environments

## Contributing

Contributions to the project are welcome. Please follow these steps:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

[Specify the license here]

## Acknowledgments

- [FastMCP](https://github.com/jlowin/fastmcp) - For the Model Context Protocol implementation
- eBay Developers Program - For API access and documentation
