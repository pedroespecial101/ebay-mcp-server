# eBay MCP Server

## Overview

This project implements a Model Context Protocol (MCP) server for eBay OAuth API integration, primarily focused on seller actions. The server uses FastMCP to expose eBay API endpoints as callable functions that can be accessed by AI assistants and other MCP clients. The project is designed to use user-level tokens rather than application-level authentication, allowing actions to be performed on behalf of a specific eBay seller account.

Additionally, the project includes an MCP Test UI that provides a web interface for testing MCP tools, allowing for interactive parameter input and result visualization without requiring an IDE or AI assistant integration.

## Key Features

- OAuth2 authentication with eBay's API using user-level tokens
- Token management system with automatic refresh capabilities
- Multiple MCP functions for interacting with eBay APIs:
  - Browse API for searching items
  - Taxonomy API for category suggestions and item aspects
  - Inventory API for retrieving offer details by SKU
- Robust error handling and token refresh logic
- Centralized logging system with timed rotation
- Server management script for easy lifecycle management
- Web-based MCP Test UI for interactive tool testing and parameter input

## Technology Stack

- **FastMCP**: Framework for building Model Context Protocol servers
- **Python 3**: Core programming language
- **eBay REST APIs**: Various endpoints for eBay platform integration
- **OAuth2**: Authentication mechanism for eBay API access
- **python-dotenv**: Environment variable management
- **httpx**: Asynchronous HTTP client for API calls
- **logging**: Standard Python logging with TimedRotatingFileHandler
- **FastAPI**: For the MCP Test UI backend
- **Jinja2**: Template engine for the MCP Test UI
- **Bootstrap 5**: Frontend framework for the MCP Test UI
- **Pydantic**: Data validation for the MCP Test UI

## Project Structure

```
ebay-mcp-server/
├── .env                    # Environment variables and tokens (gitignored)
├── CHANGELOG.md            # Documentation of changes to the project
├── README.md               # Project documentation (this file)
├── ebay_auth/              # eBay authentication module
│   └── ebay_auth.py        # OAuth implementation for eBay
├── ebay_docs/              # eBay API documentation and project reference files
├── logs/                   # Server logs directory
│   └── fastmcp_server.log  # Server log file with rotation
├── mcp_test_ui/            # Web UI for testing MCP tools
│   ├── app.py              # FastAPI application for the UI
│   ├── requirements.txt    # UI-specific dependencies
│   ├── static/             # Static assets for the UI
│   └── templates/          # Jinja2 templates for UI pages
├── src/                    # Source code directory
│   ├── ebay_service.py     # eBay service utilities
│   └── server.py           # Main MCP server implementation
├── start.sh                # MCP server management script
├── mcp_test_ui_start.py    # Script to start the MCP Test UI
├── requirements.txt        # Python dependencies
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
./start.sh

# Check logs
tail -f logs/fastmcp_server.log
```

**Important Note:** Running the `start.sh` script does not affect the IDE's MCP integration, which runs in a separate process managed by the IDE's configuration. These are two completely separate instances of the server.

#### IDE MCP Integration

For AI assistants and IDEs that support the Model Context Protocol (MCP), the server is typically configured in the IDE's MCP configuration file. A sample configuration might look like this:

```json
"Ebay API": {
  "command": "/path/to/ebay-mcp-server/.venv/bin/fastmcp",
  "args": [
    "run",
    "/path/to/ebay-mcp-server/src/server.py"
  ],
  "env": {}
}
```

This configuration tells the IDE to:
1. Run the FastMCP executable from the project's virtual environment
2. Use the `run` command (instead of the `dev` command used by `start.sh`)
3. Point to the server.py file

**Important Notes:** 
- Changes to the MCP server **code** will require restarting the MCP server process in your IDE for changes to take effect, which is separate from running the `start.sh` script.
- Authentication performed through the `trigger_ebay_login` MCP tool in the IDE does **not** require restarting the MCP server. Tokens are automatically loaded after successful authentication.

### MCP Client Integration

The server implements the Model Context Protocol, allowing AI assistants and other MCP clients to call the exposed functions directly. Available functions include:

- `test_auth()`: Test authentication and token retrieval
- `trigger_ebay_login()`: Initiates the eBay OAuth2 login flow directly from the MCP IDE
- `add(a: int, b: int)`: Simple addition function (useful for testing)
- `search_ebay_items(query: str, limit: int = 10)`: Search items on eBay
- `get_category_suggestions(query: str)`: Get category suggestions from eBay Taxonomy API
- `get_item_aspects_for_category(category_id: str)`: Get item aspects for a specific category
- `get_offer_by_sku(sku: str)`: Get offer details for a specific SKU

## Adding New Functions

To add a new function to the MCP server, follow these steps:

1. Identify the eBay API endpoint you want to expose
2. Add a new async function to `src/server.py` using the `@mcp.tool()` decorator
3. Implement the function logic using the `_execute_ebay_api_call` helper for consistent error handling
4. Follow the existing pattern for API calls:

```python
@mcp.tool()
async def your_new_function(param1: str, param2: int = 10) -> str:
    """Your function description"""
    logger.info(f"Executing your_new_function with param1='{param1}', param2={param2}.")

    async def _api_call(access_token: str, client: httpx.AsyncClient):
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        params = {"param1": param1, "param2": param2}
        url = "https://api.ebay.com/path/to/endpoint"
        
        response = await client.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.text

    async with httpx.AsyncClient() as client:
        return await _execute_ebay_api_call("your_new_function", client, _api_call)
```

5. Restart the server using `./start.sh` to make the new function available

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

## MCP Test UI

The project includes a web-based user interface for testing MCP tools directly in the browser:

### Features

- Interactive web UI for testing all available MCP tools
- Automatic parameter form generation based on tool input schemas
- Support for different parameter types (string, integer, boolean, etc.)
- Real-time tool execution with formatted results display
- Accordion-style organization of tools for easy navigation

### Usage

1. Start the MCP Test UI server:
   ```bash
   python mcp_test_ui_start.py
   ```

2. Open a browser and navigate to http://127.0.0.1:8000

3. Select a tool from the list, fill in the required parameters, and click "Execute" to test the tool

4. View the execution results and response time in the UI

## Future Plans

Potential enhancements for the project:

1. **Pydantic Integration**: Implement Pydantic models throughout the codebase for improved validation and type safety
2. **Database Integration**: Move token storage from `.env` file to a secure database
3. **Multiple User Support**: Allow the server to manage tokens for multiple eBay seller accounts
4. **More eBay APIs**: Expand the available functions to cover additional eBay APIs
5. **Enhanced Error Handling**: Improve error reporting and recovery mechanisms
6. **Expanded MCP Test UI**: Add more features to the testing interface
7. **Automated Test Suite**: Develop comprehensive tests for all components
   - Order Management API
   - Fulfillment API
   - Marketing API
   - Compliance API
4. **Rate Limiting**: Implement rate limiting to comply with eBay API usage policies
5. **Web Interface**: Add a web dashboard for monitoring the server status and token management
6. **Webhook Support**: Enable webhooks for eBay notifications
7. **Docker Container**: Containerize the application for easier deployment
8. **API Key Management**: Implement rotation and secure storage of API credentials

## Troubleshooting

### Authentication Issues

- **Missing or Invalid Tokens**: If you receive an error about missing or invalid tokens, use the `trigger_ebay_login` MCP tool to authenticate with eBay.
- **Token Refresh Failures**: If token refresh attempts fail, the system will prompt you to re-authenticate using the `trigger_ebay_login` MCP tool.
- **Authentication Flow Not Working**: Ensure your eBay application settings, especially the `EBAY_RU_NAME` and `EBAY_APP_CONFIGURED_REDIRECT_URI` in the `.env` file, are correctly configured.

### Server Issues

- **Code Changes Not Taking Effect**: After modifying the server code, restart the MCP server process in your IDE. For local testing with `start.sh`, use `./start.sh` to restart the server.
- **Multiple Authentication Attempts**: If multiple authentication attempts occur in rapid succession, you may encounter port conflicts. Wait a few moments between attempts.

### Other Common Issues

- **Authentication Failures**: Check that your eBay App credentials are correctly set in the `.env` file
- **Token Refresh Issues**: If tokens aren't refreshing, try manually re-authenticating with `python ebay_auth/ebay_auth.py login`
- **Server Won't Start**: Check the logs at `logs/fastmcp_server.log` for detailed error messages
- **Missing Dependencies**: Ensure all requirements are installed with `pip install -r requirements.txt`

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
