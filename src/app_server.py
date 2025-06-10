"""
App MCP Server - Exposes FastAPI endpoints from https://api.petetreadaway.com as MCP tools
"""
import os
import sys
import logging
import httpx
import json
from dotenv import load_dotenv

# Add the project root directory to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from fastmcp import FastMCP
from fastmcp.server.openapi import RouteMap, RouteType

# Load environment variables
load_dotenv()

# Get logger
logger = logging.getLogger(__name__)

# Configuration
API_BASE_URL = os.getenv('APP_API_BASE_URL', 'https://api.petetreadaway.com')
API_TIMEOUT = float(os.getenv('APP_API_TIMEOUT', '30.0'))

# Configurable endpoint exclusions
EXCLUDED_ENDPOINTS = [
    '/api/product-images/reorder',
    '/api/test-image-upload'
]

# Following FastMCP's recommended patterns for route mapping
# GET with path parameters → ResourceTemplate
# GET without path parameters → Resource
# All other methods → Tool

# Ensure these endpoints are exposed as tools (even if they're GET)
FORCE_AS_TOOLS = [
    '/api/products',
    '/api/categories'
]

# Debug level for detailed route mapping logs
ROUTE_MAPPING_DEBUG = os.getenv('ROUTE_MAPPING_DEBUG', 'false').lower() == 'true'

class AppMCPServer:
    """MCP Server for exposing FastAPI endpoints as MCP tools"""
    
    def __init__(self, base_url: str = API_BASE_URL, timeout: float = API_TIMEOUT):
        self.base_url = base_url
        self.timeout = timeout
        self.client = None
        self.mcp = None
        
    async def initialize(self) -> FastMCP:
        """Initialize the MCP server with OpenAPI integration"""
        logger.info(f"Initializing App MCP Server for {self.base_url}")
        
        try:
            # Create HTTP client for API requests
            self.client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers={
                    'User-Agent': 'eBay-MCP-Server/1.0',
                    'Accept': 'application/json'
                }
            )
            
            # Fetch OpenAPI specification
            logger.info("Fetching OpenAPI specification...")
            response = await self.client.get('/openapi.json')
            response.raise_for_status()
            openapi_spec = response.json()

            logger.info(f"Successfully loaded OpenAPI spec with {len(openapi_spec.get('paths', {}))} endpoints")

            # Save OpenAPI spec to file for debugging if debug is enabled
            if ROUTE_MAPPING_DEBUG:
                try:
                    with open(os.path.join(project_root, 'openapi_spec.json'), 'w') as f:
                        json.dump(openapi_spec, f, indent=2)
                    logger.info("Saved OpenAPI spec to openapi_spec.json for debugging")
                except Exception as e:
                    logger.error(f"Failed to save OpenAPI spec: {str(e)}")

            # Analyze path parameters
            path_param_analysis = {}
            for path, path_item in openapi_spec.get('paths', {}).items():
                has_params = '{' in path and '}' in path
                path_param_analysis[path] = {
                    'has_path_params': has_params,
                    'methods': list(path_item.keys()),
                    'param_names': [param[1:-1] for param in path.split('/') if param.startswith('{') and param.endswith('}')] if has_params else []
                }
                
                if ROUTE_MAPPING_DEBUG:
                    logger.info(f"Path analysis: {path} -> {path_param_analysis[path]}")

            # Fix operation IDs to be MCP-compliant before passing to FastMCP
            self._fix_operation_ids(openapi_spec)
            
            # Create custom route maps for exclusions
            route_maps = self._create_route_maps()

            # Create MCP server from OpenAPI spec
            self.mcp = FastMCP.from_openapi(
                openapi_spec=openapi_spec,
                client=self.client,
                name="App API Server",
                timeout=self.timeout,
                route_maps=route_maps
            )
            
            # Log the created components if debug is enabled
            if ROUTE_MAPPING_DEBUG:
                try:
                    # Use get_tools() and get_resources() for newer FastMCP versions
                    tools = await self.mcp.get_tools()
                    resources = await self.mcp.get_resources()
                    
                    # Log tools
                    logger.info(f"MCP Server created with {len(tools)} tools")
                    for tool in tools:
                        logger.info(f"Tool: {tool}")
                    
                    # Create a special debug file for tools
                    try:
                        with open(os.path.join(project_root, 'mcp_tools.txt'), 'w') as f:
                            for tool in tools:
                                f.write(f"{tool}\n")
                        logger.info("Saved tools to mcp_tools.txt for debugging")
                    except Exception as e:
                        logger.error(f"Failed to save tools: {str(e)}")
                    
                    # Log resources and identify resource templates
                    resource_templates = [r for r in resources if isinstance(r, str) and '{' in r]                    
                    logger.info(f"MCP Server created with {len(resources)} resources")
                    for resource in resources:
                        if isinstance(resource, str):
                            if '{' in resource:
                                logger.info(f"Resource Template: {resource}")
                            else:
                                logger.info(f"Resource: {resource}")
                        elif hasattr(resource, 'uri'):
                            uri = resource.uri
                            if '{' in uri:
                                logger.info(f"Resource Template: {uri}")
                            else:
                                logger.info(f"Resource: {uri}")
                    
                    # Create a special debug file for resources
                    try:
                        with open(os.path.join(project_root, 'mcp_resources.txt'), 'w') as f:
                            for resource in resources:
                                if isinstance(resource, str):
                                    f.write(f"{resource}\n")
                                elif hasattr(resource, 'uri'):
                                    f.write(f"{resource.uri}\n")
                        logger.info("Saved resources to mcp_resources.txt for debugging")
                    except Exception as e:
                        logger.error(f"Failed to save resources: {str(e)}")
                                
                    logger.info(f"Resource Templates (with parameters): {len(resource_templates)}")
                except Exception as e:
                    logger.error(f"Error logging MCP components: {str(e)}")
                    # Continue despite logging errors
            
            logger.info("App MCP Server initialized successfully")
            return self.mcp
            
        except Exception as e:
            logger.error(f"Failed to initialize App MCP Server: {str(e)}")
            if self.client:
                await self.client.aclose()
            raise
    
    def _create_route_maps(self) -> list[RouteMap]:
        """Create route maps for endpoint exclusions and customizations"""
        route_maps = []
        
        # 1. First, exclude specific endpoints (highest priority)
        for endpoint in EXCLUDED_ENDPOINTS:
            route_maps.append(
                RouteMap(
                    methods=["POST", "GET", "PUT", "DELETE", "PATCH"],  # All methods
                    pattern=f"^{endpoint}$",  # Exact match for the endpoint
                    route_type=RouteType.IGNORE
                )
            )
            logger.info(f"Configured exclusion for endpoint: {endpoint}")

        # 2. Force specified endpoints to be exposed as tools (even if they're GET)
        for endpoint in FORCE_AS_TOOLS:
            route_maps.append(
                RouteMap(
                    methods=["GET"],
                    pattern=f"^{endpoint}$",  # Exact match for the endpoint
                    route_type=RouteType.TOOL
                )
            )
            logger.info(f"Forcing endpoint as tool: GET {endpoint}")

        # 3. GET with path parameters → ResourceTemplate (standard FastMCP pattern)
        route_maps.append(
            RouteMap(
                methods=["GET"], 
                pattern=r".*\{.*\}.*", 
                route_type=RouteType.RESOURCE_TEMPLATE
            )
        )
        logger.info("Following FastMCP standard: GET endpoints with path parameters as RESOURCE_TEMPLATE")
        
        # 4. GET without path parameters → Resource (standard FastMCP pattern)
        route_maps.append(
            RouteMap(
                methods=["GET"], 
                pattern=r".*", 
                route_type=RouteType.RESOURCE
            )
        )
        logger.info("Following FastMCP standard: GET endpoints without path parameters as RESOURCE")
        
        # 5. All other methods → Tool (standard FastMCP pattern)
        route_maps.append(
            RouteMap(
                methods=["*"], 
                pattern=r".*", 
                route_type=RouteType.TOOL
            )
        )
        logger.info("Following FastMCP standard: All other endpoints as TOOL")
        
        return route_maps

    def _fix_operation_ids(self, openapi_spec):
        """Fix operation IDs to be MCP compliant, ensure they're unique and properly formatted"""
        for path, path_item in openapi_spec.get('paths', {}).items():
            # Track if this path has path parameters
            has_path_params = '{' in path and '}' in path
            
            for method, operation in path_item.items():
                # Skip non-operation fields like 'parameters'
                if method in ['parameters']:
                    continue

                # Ensure operation ID exists and meets MCP naming requirements
                if 'operationId' in operation:
                    # Replace dashes with underscores for MCP compatibility
                    operation['operationId'] = operation['operationId'].replace('-', '_')

                    # Normalize API path for uniqueness in operation ID
                    path_part = path.replace('/', '_')
                    path_part = path_part.replace('{', '')
                    path_part = path_part.replace('}', '')

                    # Create canonical operation ID: function_path_method
                    # This ensures uniqueness and MCP compatibility
                    canonical_id = f"{operation['operationId']}_{method}"
                    operation['operationId'] = canonical_id
                    
                    # Add metadata to help route mapping decisions
                    # This will help FastMCP correctly identify resource templates
                    if has_path_params:
                        operation['x-mcp-has-path-params'] = True
                        operation['x-mcp-path'] = path

                    logger.info(f"Fixed operation ID: {canonical_id}")

    async def cleanup(self):
        """Clean up resources"""
        if self.client:
            await self.client.aclose()
            logger.info("HTTP client closed")

# Create global server instance
app_server = AppMCPServer()

# Create the MCP server instance at module level (like main_server.py)
import asyncio

# Initialize the server synchronously at module level
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
try:
    mcp = loop.run_until_complete(app_server.initialize())
    logger.info("App MCP server initialized successfully")
finally:
    loop.close()

# When running this file directly, start the MCP server
# Add run method to match main_server.py pattern
def run():
    """Run the App MCP server"""
    logger.info("Starting App MCP server with stdio transport...")
    logger.info("Server is configured with FastAPI OpenAPI integration")
    mcp.run()

if __name__ == "__main__":
    logger.info("Starting App MCP server with stdio transport...")
    logger.info("Server exposes FastAPI endpoints from https://api.petetreadaway.com")
    mcp.run()
