# eBay MCP Server

## Overview

This project implements a Model Context Protocol (MCP) server for eBay OAuth API integration, primarily focused on seller actions. The server uses FastMCP to expose eBay API endpoints as callable functions that can be accessed by AI assistants and other MCP clients. The project is designed to use user-level tokens rather than application-level authentication, allowing actions to be performed on behalf of a specific eBay seller account.

Additionally, you can test MCP tools using **MCP Inspector** — an open-source browser interface available at <https://github.com/modelcontextprotocol/inspector>.

## Key Features

- OAuth2 authentication with eBay's API using user-level tokens
- Token management system with automatic refresh capabilities
- Multiple MCP functions for interacting with eBay APIs:
  - Browse API for searching items
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
├── .env                    # Environment variables and tokens (gitignored)
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
├── start.sh                # MCP server management script for local testing
├── requirements.txt        # Python dependencies
├── src/                    # Source code directory
│   ├── ebay_mcp/           # Modular MCP servers for eBay APIs
│   │   ├── auth/           # Authentication API server
│   │   │   └── server.py   # Auth MCP tools implementation
│   │   ├── browse/         # Browse API server
│   │   │   └── server.py   # Browse MCP tools implementation
│   │   ├── inventory/      # Inventory API server
│   │   │   ├── server.py   # Inventory MCP base implementation
│   │   │   ├── get_inventory_items.py        # Get inventory items with pagination tool
│   │   │   ├── update_offer.py  # Update offer tool implementation
│   │   │   ├── withdraw_offer.py # Withdraw offer tool implementation
│   │   │   ├── listing_fees.py  # Listing fees tool implementation
│   │   │   └── manage_offer.py  # Comprehensive offer management tool (create, modify, withdraw, publish, get)
│   │   └── taxonomy/       # Taxonomy API server
│   │       └── server.py   # Taxonomy MCP tools implementation
│   ├── other_tools_mcp/    # Other utility tool servers
│   │   ├── database/       # Database utility tools
│   │   │   └── server.py   # Database MCP tools implementation
│   │   └── tests/          # Test utility tools
│   │       └── server.py   # Test MCP tools implementation
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

4. Create a `.env` file in the project root with the following variables:
   ```
   EBAY_CLIENT_ID=<your_client_id>
   EBAY_CLIENT_SECRET=<your_client_secret>
   EBAY_RU_NAME=<your_runame>
   EBAY_APP_CONFIGURED_REDIRECT_URI=<your_redirect_uri>
   
   # The following will be populated by the authentication process
   # EBAY_USER_ACCESS_TOKEN=<access_token>
   # EBAY_USER_REFRESH_TOKEN=<refresh_token>
   # EBAY_USER_ID=<user_id>
   # EBAY_USER_NAME=<username>
   ```

5. Run the authentication flow to get user tokens:
   ```bash
   python ebay_auth/ebay_auth.py login
   ```

## Usage

### Server Management

#### Local Development and Testing

The `start.sh` script is provided for local development and testing purposes. It is **not** used by the IDE's MCP integration:

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
"Ebay API": {
  "command": "/path/to/ebay-mcp-server/.venv/bin/fastmcp",
  "args": [
    "run",
    "/path/to/ebay-mcp-server/src/main_server.py"
  ],
  "env": {}
}
```

This configuration tells the IDE to:
1. Run the FastMCP executable from the project's virtual environment
2. Use the `run` command (instead of the `dev` command used by `start.sh`)
3. Point to the `main_server.py` file

**Important Notes:** 
- Changes to the MCP server **code** will require restarting the MCP server process in your IDE for changes to take effect, which is separate from running the `start.sh` script.
- Authentication performed through the `trigger_ebay_login` MCP tool in the IDE does **not** require restarting the MCP server. Tokens are automatically loaded after successful authentication.

### MCP Client Integration

The server implements the Model Context Protocol, allowing AI assistants and other MCP clients to call the exposed functions directly. Available functions include:

### Authentication & Testing Tools
- `test_auth()`: Test authentication and token retrieval
- `trigger_ebay_login()`: Initiates the eBay OAuth2 login flow directly from the MCP IDE
- `add(a: int, b: int)`: Simple addition function (useful for testing)

### Browse API Tools
- `search_ebay_items(query: str, limit: int = 10)`: Search items on eBay

### Taxonomy API Tools
- `get_category_suggestions(query: str)`: Get category suggestions from eBay Taxonomy API
- `get_item_aspects_for_category(category_id: str)`: Get item aspects for a specific category

### Inventory API Tools
- `get_inventory_items(limit: int = 25, offset: int = 0)`: Retrieve multiple inventory items with pagination support
- `get_offer_by_sku(sku: str)`: Get offer details for a specific SKU
- `manage_inventory_item(sku: str, action: str, item_data: Optional[dict])`: Manages eBay inventory items. Actions include 'create', 'modify', 'get', 'delete'. For 'create' and 'modify', the `item_data` payload follows a limited-field schema (title, description, identifiers, condition, availability) as defined by the InventoryItemDataForManage model.
- `manage_offer(sku: str, action: str, offer_data: Optional[dict])`: Manages eBay offers. Actions include 'create', 'modify', 'withdraw', 'publish', 'get'. The `offer_data` parameter is a complex object required for 'create' and 'modify' actions; refer to the tool's auto-generated schema for detailed field names (using `camelCase`) and descriptions.
- `get_listing_fees(offer_ids: list)`: Get listing fees for unpublished offers

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

6. Restart the server using `./start.sh` to make the new function available

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
class ListingFeeResponse(EbayBaseModel):
    """Response model for get_listing_fees."""
    
    feeSummaries: List[FeeSummary] = Field(default_factory=list)
    warnings: Optional[List[Warning]] = None
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
5. Tokens are stored in the `.env` file
6. The MCP server uses these tokens for API calls

### Method 2: In-IDE MCP Authentication (Recommended)

1. AI assistant or user calls the `trigger_ebay_login` MCP tool
2. Browser opens to eBay login page
3. After login, eBay redirects to the configured redirect URI
4. Tokens are automatically stored in the `.env` file
5. The MCP server immediately begins using the new tokens without requiring a restart

In both cases, when the access token expires, it automatically refreshes using the refresh token. If the refresh token also expires or becomes invalid, the system will prompt for re-authentication using the `trigger_ebay_login` tool.

## Tool Testing (MCP Inspector)

To interactively explore and execute MCP tools in your browser, use [MCP Inspector](https://github.com/modelcontextprotocol/inspector):

1. Ensure your FastMCP server is running (e.g., via `./start.sh`).
2. Start MCP Inspector with the provided script:
   ```bash
   ./start_mcp_inspector.sh
   ```
3. Open the printed URL in your browser and point the Inspector at your local MCP server endpoint.

## Future Plans

Potential enhancements for the project:

1. **Database Integration**: Move token storage from `.env` file to a secure database
2. **Multiple User Support**: Allow the server to manage tokens for multiple eBay seller accounts
3. **More eBay APIs**: Expand the available functions to cover additional eBay APIs
4. **Expanded MCP Inspector**: Add more features to the testing interface
5. **Automated Test Suite**: Develop comprehensive tests for all components
   - Order Management API
   - Fulfillment API
   - Marketing API
   - Compliance API
6. **Rate Limiting**: Implement rate limiting to comply with eBay API usage policies
7. **Web Interface**: Add a web dashboard for monitoring the server status and token management
8. **Webhook Support**: Enable webhooks for eBay notifications
9. **Docker Container**: Containerize the application for easier deployment
10. **API Key Management**: Implement rotation and secure storage of API credentials

## Security Considerations

- The `.env` file contains sensitive credentials and should never be committed to version control
- Consider implementing token encryption at rest if deploying to production
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
