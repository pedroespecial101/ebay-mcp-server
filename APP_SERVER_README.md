# App MCP Server

This is an independent MCP server that exposes FastAPI endpoints from https://api.petetreadaway.com as MCP tools and resources using FastMCP's built-in OpenAPI integration.

## Features

- **Automatic Tool & Resource Generation**: Uses FastMCP's `from_openapi()` to automatically create MCP tools, resources, and resource templates
- **Configurable Exclusions**: Excludes sensitive endpoints like `/api/product-images/reorder` and `/api/test-image-upload`
- **Independent Operation**: Runs separately from the eBay MCP server
- **Robust Error Handling**: Proper authentication, timeout handling, and resource cleanup

## Route Mapping

The server follows FastMCP's recommended route mapping patterns:

| OpenAPI Route | Example | MCP Component |
|---------------|---------|---------------|
| `GET` with path params | `GET /api/products/{id}` | **Resource Template** |
| `GET` without path params | `GET /api/products` | **Resource** |
| `POST`, `PUT`, etc. | `POST /api/products` | **Tool** |

### Route Mapping Priority

1. **Exclusions** - Specific endpoints that should not be exposed
2. **Force As Tools** - GET endpoints that should be exposed as tools
3. **GET with path parameters** → Resource Templates
4. **GET without path parameters** → Resources
5. **All other methods** → Tools

## Important Note on Resource Templates

Resource Templates (endpoints with path parameters) are accessed using the `get_resource_templates()` method, not the standard `get_resources()` method:

```python
# Get normal resources
resources = await mcp.get_resources()

# Get resource templates (for path parameter endpoints)
resource_templates = await mcp.get_resource_templates()
```

## Quick Start

### Using with MCP Test UI (Recommended)

The server works exactly like the eBay MCP server. You can switch between servers in the MCP Test UI:

```bash
./start_mcp_test_ui.sh
```

Then in the UI, set the server path to:
- **For eBay tools**: `src/main_server.py` (default)
- **For App tools**: `src/app_server.py`

### Direct Testing

You can also test the server directly (it will wait for MCP client connections):

```bash
python src/app_server.py
```

### Multiple Servers

Yes! You can absolutely have both servers in this project:
- **eBay MCP Server** (`src/main_server.py`) - For eBay API tools
- **App MCP Server** (`src/app_server.py`) - For FastAPI app tools

Simply switch the `MCP_SERVER_PATH` in your `.env` file or change it in the MCP Test UI.

## Configuration

The server can be configured using environment variables:

```bash
# Optional: Override the API base URL (default: https://api.petetreadaway.com)
export APP_API_BASE_URL="https://your-api.example.com"

# Optional: Set request timeout in seconds (default: 30.0)
export APP_API_TIMEOUT="60.0"
```

## Available Tools and Resources

The server automatically generates:

- **13 Tools** (POST, PUT, PATCH, DELETE operations) - All MCP-compliant names
- **3 Resources** (GET operations without path parameters)
- **1 Resource Template** (GET operations with path parameters like `/api/products/{product_id}`)
- **2 Excluded endpoints** (configurable)

### Sample Tools Available:

- `product_processing_page_products_get` - Product processing page
- `get_category_suggestions_api_products_product_id_category_sugges` - Get eBay category suggestions
- `update_product_field_api_products_product_id_update_post` - Update product field
- `bulk_process_products_api_products_bulk_process_post` - Bulk process products
- `publish_product_to_ebay_api_products_product_id_publish_to_ebay` - Publish to eBay
- And 8 more tools...

### Sample Resources Available:

- `resource://openapi/get_products_api_products_get` - Get products list
- `resource://openapi/health_check_health_get` - Health check
- `resource://openapi/root_get` - Root endpoint

### Sample Resource Templates Available:

- `resource://openapi/get_product_by_id_api_products_product_id_get/{product_id}` - Get product by ID

## Customizing Exclusions

To modify which endpoints are excluded, edit the `EXCLUDED_ENDPOINTS` list in `src/app_server.py`:

```python
EXCLUDED_ENDPOINTS = [
    '/api/product-images/reorder',
    '/api/test-image-upload',
    # Add more endpoints to exclude here
]
```

## Troubleshooting

### "Already running asyncio in this thread" Error

This error should not occur with the current implementation. The server now follows the same pattern as `src/main_server.py` and initializes properly at the module level.

If you still encounter this error, it means there's an environment issue. The server should work exactly like the eBay MCP server.

### Connection Issues

If the server can't connect to the API:

1. Check your internet connection
2. Verify the API is accessible: `curl https://api.petetreadaway.com/openapi.json`
3. Check firewall settings

### MCP Client Integration

To use this server with MCP clients (like Claude Desktop), configure your client to point to:

```
/path/to/your/project/run_app_server.py
```

## Architecture

The server follows the established project patterns:

- **Modular Design**: Independent from the eBay MCP server
- **Consistent Logging**: Uses the same logging infrastructure
- **Error Handling**: Follows existing error handling patterns
- **Resource Management**: Proper async cleanup and resource management

## Development

This server serves as a template for exposing other FastAPI applications as MCP servers. The key components are:

1. **OpenAPI Integration**: Automatic tool generation from OpenAPI specs
2. **Route Mapping**: Configurable endpoint exclusions and customizations
3. **Client Management**: Proper HTTP client lifecycle management
4. **MCP Compliance**: Full compatibility with MCP protocol standards

## Testing

The server has been tested with:

- ✅ Server initialization and OpenAPI spec loading
- ✅ Tool and resource discovery
- ✅ Endpoint exclusion functionality
- ✅ MCP test UI compatibility
- ✅ Proper error handling and cleanup
