#!/usr/bin/env python
"""Test script to verify the App MCP Server's exposed endpoints"""
import asyncio
import os
import sys
import json
from pprint import pprint

# Add the project root directory to the Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_root)

# Import the App MCP server
from src.app_server import app_server

async def test_mcp_endpoints():
    """Test the MCP endpoints exposed by the App MCP server"""
    print("Testing App MCP Server...")
    
    try:
        # Get the MCP server instance
        mcp = app_server.mcp
        
        # Get all tools
        print("\n=== TOOLS ===")
        tools = await mcp.get_tools()
        print(f"Found {len(tools)} tools:")
        for i, tool in enumerate(tools, 1):
            print(f"{i}. {tool}")
            
            # Check if tool contains 'api/products' in the name or path
            if hasattr(tool, '__dict__'):
                tool_dict = tool.__dict__
                if 'path' in tool_dict and 'api/products' in str(tool_dict['path']):
                    print(f"   - PRODUCTS TOOL: {tool_dict['name']}")
                    print(f"   - Path: {tool_dict.get('path')}")
        
        # Get all resources
        print("\n=== RESOURCES ===")
        resources = await mcp.get_resources()
        print(f"Found {len(resources)} resources:")
        
        # Get the raw response as well to inspect
        try:
            print("\n=== RAW MCP INSPECTION ===")
            if hasattr(mcp, '_openapi_server'):
                openapi_server = mcp._openapi_server
                if hasattr(openapi_server, '_route_maps'):
                    print("Route Maps:")
                    for i, route_map in enumerate(openapi_server._route_maps):
                        print(f"{i}: {route_map}")
                if hasattr(openapi_server, '_resources'):
                    print(f"\nResources Count: {len(openapi_server._resources)}")
                if hasattr(openapi_server, '_resource_templates'):
                    print(f"Resource Templates Count: {len(openapi_server._resource_templates)}")
                    for template in openapi_server._resource_templates:
                        print(f"  - Template: {template}")
        except Exception as e:
            print(f"Error during raw MCP inspection: {e}")
        
        # Try to get resource templates specifically if available
        try:
            print("\n=== RESOURCE TEMPLATES ===")
            # In FastMCP, resource templates might be accessed via separate API or inspection
            # This is exploratory to see what's available
            if hasattr(mcp, 'get_resource_templates'):
                templates = await mcp.get_resource_templates()
                print(f"Found {len(templates)} resource templates via get_resource_templates()")
                for i, template in enumerate(templates, 1):
                    print(f"{i}. {template}")
            elif hasattr(mcp, '_resource_templates'):
                templates = mcp._resource_templates
                print(f"Found {len(templates)} resource templates via _resource_templates attribute")
                for i, template in enumerate(templates, 1):
                    print(f"{i}. {template}")
            else:
                print("No specific resource template accessor found in MCP server")
        except Exception as e:
            print(f"Error accessing resource templates: {e}")
        
        # Save full resources details to a debug file
        try:
            with open(os.path.join(project_root, 'resource_details.json'), 'w') as f:
                resource_list = []
                for r in resources:
                    if hasattr(r, '__dict__'):
                        resource_list.append(r.__dict__)
                    else:
                        resource_list.append(str(r))
                json.dump(resource_list, f, default=str, indent=2)
        except:
            print("Could not save resource details to file")
        
        # Detailed inspection of resources
        products_endpoints = []
        param_endpoints = []
        
        for i, resource in enumerate(resources, 1):
            # Display basic info
            if hasattr(resource, 'uri'):
                print(f"{i}. {resource.uri}")
                uri = resource.uri
            else:
                print(f"{i}. {resource}")
                uri = str(resource)
                
            # Check if this is a products endpoint
            if 'api/products' in uri:
                products_endpoints.append(uri)
                print(f"   - PRODUCTS ENDPOINT")
                
            # Check if this is a path parameter endpoint
            if '{' in uri:
                param_endpoints.append(uri)
                print(f"   - PATH PARAMETER ENDPOINT")
                
            # Inspect more details if possible
            if hasattr(resource, '__dict__'):
                resource_dict = resource.__dict__
                print(f"   - Resource Dict: {resource_dict}")
                if 'path' in resource_dict and 'api/products' in str(resource_dict['path']):
                    print(f"   - Path: {resource_dict.get('path')}")
                    
                # Check for template markers
                if 'is_template' in resource_dict and resource_dict['is_template']:
                    print(f"   - IS TEMPLATE: Yes")
                elif 'template' in resource_dict and resource_dict['template']:
                    print(f"   - HAS TEMPLATE: {resource_dict['template']}")
            
        # Summarize products endpoints
        print("\n=== /api/products ENDPOINTS ===")
        print(f"Found {len(products_endpoints)} /api/products endpoints:")
        for i, endpoint in enumerate(products_endpoints, 1):
            print(f"{i}. {endpoint}")
            
        # Summarize path parameter endpoints
        print("\n=== PATH PARAMETER ENDPOINTS ===")
        print(f"Found {len(param_endpoints)} endpoints with path parameters:")
        for i, endpoint in enumerate(param_endpoints, 1):
            print(f"{i}. {endpoint}")
            
        # Check tool mappings from debug files
        try:
            print("\n=== EXAMINING DEBUG FILES ===")
            with open(os.path.join(project_root, 'openapi_spec.json'), 'r') as f:
                spec = json.load(f)
                product_paths = [path for path in spec['paths'].keys() if 'api/products' in path]
                print(f"OpenAPI spec has {len(product_paths)} /api/products paths:")
                for path in product_paths:
                    print(f"  - {path}")
                    
                    # Check if path has parameters
                    if '{' in path:
                        print(f"    * Has path parameters")
                        # Check operation details
                        path_item = spec['paths'][path]
                        for method, operation in path_item.items():
                            if method not in ['parameters', 'summary', 'description']:
                                print(f"    * Method: {method}")
                                if 'operationId' in operation:
                                    print(f"    * Operation ID: {operation['operationId']}")
                                if 'x-mcp-has-path-params' in operation:
                                    print(f"    * Has x-mcp-has-path-params: {operation['x-mcp-has-path-params']}")
        except Exception as e:
            print(f"Could not read debug files: {e}")
            
    except Exception as e:
        print(f"Error testing MCP endpoints: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_mcp_endpoints())
