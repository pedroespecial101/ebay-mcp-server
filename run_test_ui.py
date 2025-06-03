#!/usr/bin/env python
"""
Run script for the MCP Test UI
"""
import os
import sys
from pathlib import Path

# Add the project root to the path
sys.path.append(str(Path(__file__).parent))

# Run the MCP Test UI
if __name__ == "__main__":
    import uvicorn
    from mcp_test_ui.app import app
    
    uvicorn.run(app, host="127.0.0.1", port=8080)
