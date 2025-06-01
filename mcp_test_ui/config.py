import logging
from typing import List, Optional, Any

# Global variables for MCP Test UI
mcp_server_path: Optional[str] = None
cached_tools: List[Any] = []  # Will be List[MCPTool] after MCPTool is defined/imported

# Configure logging for this module
logger = logging.getLogger("mcp_config")

# You can add other shared configurations here as needed
