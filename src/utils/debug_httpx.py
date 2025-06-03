"""
Enhanced HTTPX client with debug capabilities for MCP server.
This module provides request and response tracking to enable detailed debugging.
"""
import httpx
import logging
from typing import Any, Dict, Optional, Union
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get logger
logger = logging.getLogger(__name__)

# Determine if we're in DEBUG mode
DEBUG_MODE = os.getenv('MCP_LOG_LEVEL', 'NORMAL').upper() == 'DEBUG'

class DebugAsyncClient(httpx.AsyncClient):
    """
    Enhanced AsyncClient that tracks the last request and response for debugging purposes.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_request = None
        self._last_response = None
        
    async def request(self, *args, **kwargs) -> httpx.Response:
        """Override the request method to track requests and responses."""
        # Store the request
        request = httpx.Request(*args, **kwargs)
        self._last_request = request
        
        # Execute the request
        response = await super().request(*args, **kwargs)
        
        # Store the response
        self._last_response = response
        
        return response
        
    async def get(self, *args, **kwargs) -> httpx.Response:
        """Override the get method for convenience."""
        response = await super().get(*args, **kwargs)
        self._last_request = response.request
        self._last_response = response
        return response
        
    async def post(self, *args, **kwargs) -> httpx.Response:
        """Override the post method for convenience."""
        response = await super().post(*args, **kwargs)
        self._last_request = response.request
        self._last_response = response
        return response
        
    async def put(self, *args, **kwargs) -> httpx.Response:
        """Override the put method for convenience."""
        response = await super().put(*args, **kwargs)
        self._last_request = response.request
        self._last_response = response
        return response
        
    async def delete(self, *args, **kwargs) -> httpx.Response:
        """Override the delete method for convenience."""
        response = await super().delete(*args, **kwargs)
        self._last_request = response.request
        self._last_response = response
        return response
        
    async def patch(self, *args, **kwargs) -> httpx.Response:
        """Override the patch method for convenience."""
        response = await super().patch(*args, **kwargs)
        self._last_request = response.request
        self._last_response = response
        return response
        
def create_debug_client(*args, **kwargs) -> Union[DebugAsyncClient, httpx.AsyncClient]:
    """
    Creates either a DebugAsyncClient or a standard httpx.AsyncClient based on the DEBUG_MODE setting.
    
    Returns:
        Either a DebugAsyncClient (if DEBUG_MODE=True) or standard httpx.AsyncClient
    """
    if DEBUG_MODE:
        return DebugAsyncClient(*args, **kwargs)
    else:
        return httpx.AsyncClient(*args, **kwargs)
