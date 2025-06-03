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
  - Inventory management (update offers, withdraw offers, get listing fees)
- Pydantic models for request/response validation and type safety
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
- **Pydantic**: Data validation and type safety throughout the codebase (MCP tools and Test UI)

## Project Structure

```
ebay-mcp-server/
├── .env                    # Environment variables and tokens (gitignored)
├── CHANGELOG.md            # Documentation of changes to the project
├── README.md               # Project documentation (this file)
├── _archive/               # Archived legacy files and documentation
├── ebay_auth/              # eBay authentication module
│   ├── __init__.py         # Package initialization
│   ├── ebay_auth.py        # OAuth implementation for eBay
│   └── requirements.txt    # Auth module specific dependencies
├── ebay_docs/              # eBay API documentation and project reference files
├── logs/                   # Server logs directory
│   └── fastmcp_server.log  # Server log file with rotation
├── mcp_test_ui/            # Web UI for testing MCP tools
│   ├── app.py              # FastAPI application for the UI
│   ├── config.py           # Shared configuration for MCP UI
│   ├── mcp_utils.py        # Utility functions for MCP tools integration
│   ├── models.py           # Pydantic models for MCP UI
│   ├── routes_mcp.py       # FastAPI routes for MCP tool testing
│   ├── requirements.txt    # UI-specific dependencies
│   ├── static/             # Static assets for the UI
│   └── templates/          # Jinja2 templates for UI pages
├── src/                    # Source code directory
│   ├── ebay_mcp/           # Modular MCP servers for eBay APIs
│   │   ├── auth/           # Authentication API server
│   │   │   └── server.py   # Auth MCP tools implementation
│   │   ├── browse/         # Browse API server
│   │   │   └── server.py   # Browse MCP tools implementation
│   │   ├── inventory/      # Inventory API server
│   │   │   ├── server.py   # Inventory MCP base implementation
│   │   │   ├── update_offer.py  # Update offer tool implementation
│   │   │   ├── withdraw_offer.py # Withdraw offer tool implementation
│   │   │   └── listing_fees.py  # Listing fees tool implementation
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
├── start.sh                # MCP server management script for local testing
├── start_mcp_test_ui.sh    # Script to start the MCP Test UI server
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

- `test_auth()`: Test authentication and token retrieval
- `trigger_ebay_login()`: Initiates the eBay OAuth2 login flow directly from the MCP IDE
- `add(a: int, b: int)`: Simple addition function (useful for testing)
- `search_ebay_items(query: str, limit: int = 10)`: Search items on eBay
- `get_category_suggestions(query: str)`: Get category suggestions from eBay Taxonomy API
- `get_item_aspects_for_category(category_id: str)`: Get item aspects for a specific category
- `get_offer_by_sku(sku: str)`: Get offer details for a specific SKU
- `update_offer(offer_id: str, sku: str, marketplace_id: str, price: float, available_quantity: int)`: Update an existing offer
- `withdraw_offer(offer_id: str)`: Withdraw (delete) an existing offer
- `get_listing_fees(offer_ids: list)`: Get listing fees for unpublished offers

## Adding New Functions

To add a new function to the MCP server, follow these steps:

1. Identify the eBay API endpoint you want to expose
2. Create appropriate Pydantic models in `src/models/` for request parameters and responses
3. Add a new async function to `src/main_server.py` using the `@mcp.tool()` decorator
4. Implement the function logic using the `_execute_ebay_api_call` helper for consistent error handling
5. Follow the existing pattern for API calls with Pydantic validation:

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
   ./start_mcp_test_ui.sh
   ```

2. Open a browser and navigate to http://127.0.0.1:8000

3. Select a tool from the list, fill in the required parameters, and click "Execute" to test the tool

4. View the execution results and response time in the UI

## Future Plans

Potential enhancements for the project:

1. **Database Integration**: Move token storage from `.env` file to a secure database
2. **Multiple User Support**: Allow the server to manage tokens for multiple eBay seller accounts
3. **More eBay APIs**: Expand the available functions to cover additional eBay APIs
4. **Expanded MCP Test UI**: Add more features to the testing interface
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

## Pydantic Integration

This project extensively uses Pydantic for data validation, type safety, and API interaction:

### Key Benefits

- **Type Safety**: All MCP tools use Pydantic models for request parameters and responses
- **Input Validation**: Automatic validation of parameters with clear error messages
- **Structured Responses**: API responses are parsed into Pydantic models for easier data access
- **Consistent Error Handling**: Standardized approach to error handling across all MCP tools
- **Documentation**: Models serve as self-documenting code with descriptive field attributes

### Model Organization

Pydantic models are organized into several modules:

- `src/models/base.py`: Base models for all eBay-related objects
- `src/models/auth.py`: Authentication-related models
- `src/models/ebay/*.py`: eBay API-specific models organized by API domain
- `src/models/mcp_tools.py`: Parameter and response models for MCP tools
- `src/models/config/settings.py`: Configuration models for server settings

### MCP Tool Pattern

All MCP tools follow this pattern:

1. Use parameter models to validate input
2. Use request models to structure API calls
3. Use response models to parse API responses
4. Return structured data while maintaining backward compatibility

```python
@mcp.tool()
async def example_tool(param1: str, param2: int) -> str:
    # Validate parameters using Pydantic model
    try:
        params = ExampleParams(param1=param1, param2=param2)
        
        async def _api_call(access_token: str, client: httpx.AsyncClient):
            # Create API request using Pydantic model
            request = ExampleRequest(field1=params.param1, field2=params.param2)
            # Make API call...
            # Parse response using Pydantic model
            response_model = ExampleResponse.parse_obj(result_json)
            return response.text  # Return original JSON for backward compatibility
            
        # Execute API call with error handling
        return await _execute_ebay_api_call("example_tool", client, _api_call)
    except Exception as e:
        # Handle errors
        return f"Error: {str(e)}"
```

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

## Development Gotchas and Troubleshooting

### Pydantic Parameter Type Handling

- **ID Fields as Strings**: Many eBay API endpoints expect IDs (like `category_id`, `offer_id`, etc.) as strings, even when they contain only digits. The MCP Test UI and Pydantic models are configured to handle this conversion automatically.

- **Type Conversion in MCP Test UI**: The MCP Test UI performs automatic type conversion of form inputs. For example, a string input that looks numeric ("31388") is automatically converted to an integer before being sent to the MCP server. This can cause Pydantic validation errors when string parameters are expected. The solution is:
  1. In `mcp_test_ui/app.py`, string fields are preserved using the `string_field_names` list
  2. In Pydantic models, field validators are added to convert values to strings when needed

- **FastMCP Parameter Validation**: FastMCP performs validation before Pydantic validators run. If a parameter is defined as `str` in an MCP tool function signature but an integer is provided, FastMCP will reject it before the parameter reaches the Pydantic model.

### Server Lifecycle Management

- **Multiple Server Instances**: Be aware that running `./start.sh start` and the IDE's MCP integration create separate instances of the server. Changes to one don't affect the other.

- **Port Conflicts**: If the MCP Test UI fails to start due to port conflicts, use the command `lsof -ti:8000 | xargs kill -9` to clear any processes using port 8000.

- **Environment Variables**: Changes to the `.env` file require restarting the server for them to take effect. This applies to both the standalone server and the IDE's MCP integration.

## Tips for AI Agents

### General Development Practices

- **Commit Early and Often**: Before making significant code changes, remind the user to commit their current state to Git or create a tag.

- **Modular Solutions**: Prefer modular solutions that result in smaller, more maintainable files. If a file exceeds 500 lines, consider refactoring it into smaller components.

- **Clean Code**: Avoid code duplication and check for similar functionality elsewhere in the codebase before implementing new features.

- **Virtual Environment**: Always use the `.venv` virtual environment (not `venv`) for Python operations in this project.

### MCP and Pydantic Development

- **Test-Driven Development**: When implementing new MCP tools or modifying existing ones, first create a test script or use the MCP Test UI to verify functionality.

- **Parameter Type Safety**: Always add Pydantic field validators for any parameter that might receive mixed types, especially ID fields that should be strings but might be provided as integers.

- **Response Models**: Create comprehensive response models that capture the full structure of API responses, using optional fields for elements that might not always be present.

- **Error Handling**: Implement robust error handling with descriptive error messages. Use try-except blocks around JSON parsing and API calls with specific error types.

## AI Agent Autonomous Testing Procedure

This section provides guidance for AI agents on how to autonomously test and debug the eBay MCP Server, based on the successful approach used in this project.

### Testing MCP Tools

1. **Server Setup**:
   - Start the MCP server using `./start.sh restart`
   - Start the MCP Test UI with `./start_mcp_test_ui.sh`
   - Create a browser preview for the UI at `http://127.0.0.1:8000`

2. **Direct API Testing**:
   - Use curl commands to test MCP tools directly via the API endpoint:
     ```bash
     curl -X POST -H "Content-Type: application/x-www-form-urlencoded" -d "param1=value1&param2=value2" http://127.0.0.1:8000/execute/tool_name
     ```
   - This allows testing with exact parameter values and seeing raw responses

3. **Browser UI Testing**:
   - Use the browser preview to interact with the MCP Test UI
   - Fill out the form for the tool you want to test and submit
   - Inspect the response and any error messages

4. **Debugging Process**:
   - If a tool fails with a validation error, inspect the error message for specific details
   - Check the parameter types expected by the tool's Pydantic model
   - Look for type conversion issues in the MCP Test UI's `app.py` file
   - Add or modify field validators in the Pydantic models to handle problematic inputs
   - Restart both servers and test again

5. **Iterative Improvement**:
   - Start with a working test case and progressively introduce more complex parameters
   - Document all errors and their solutions in the CHANGELOG.md
   - After each fix, test all previously problematic tools to ensure they still work

### Logging and Error Inspection

- Monitor server logs: `tail -f logs/fastmcp_server.log`
- Check MCP Test UI console output for client-side errors
- Add debug logging statements in the code to track parameter values and types

### Validation and Verification

When validating fixes, verify:

1. The tool accepts all valid parameter types (strings, integers, etc.)
2. The tool correctly handles edge cases (empty strings, zeros, etc.)
3. The fix doesn't break other tools or functionality
4. The solution is robust against future changes

This autonomous testing approach enables AI agents to effectively identify, debug, and fix issues in the MCP server without requiring constant human intervention.

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
