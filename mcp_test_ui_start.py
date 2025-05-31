#!/usr/bin/env python3
"""
MCP Test UI Launcher Script

This script provides a convenient way to start the MCP Test UI web interface
for testing MCP tools without having to use an IDE or LLM environment.
"""

import argparse
import os
import sys
import subprocess
from pathlib import Path

# Add the project root to Python path
sys.path.append(str(Path(__file__).parent))

# Import the UI app
from mcp_test_ui.app import run_server

def kill_process_on_port(port):
    """Kill any process currently using the specified port."""
    try:
        # Check if we're on Windows or Unix-like system
        if os.name == 'nt':  # Windows
            result = subprocess.run(
                f'netstat -ano | findstr :{port}',
                shell=True, text=True, capture_output=True
            )
            if result.stdout.strip():
                # Extract PID and kill it
                for line in result.stdout.strip().split('\n'):
                    if f':{port}' in line:
                        pid = line.strip().split()[-1]
                        subprocess.run(f'taskkill /F /PID {pid}', shell=True)
                        print(f"Killed process {pid} that was using port {port}")
        else:  # Unix-like (macOS, Linux)
            # Use lsof to find and kill the process
            result = subprocess.run(
                f'lsof -ti:{port}',
                shell=True, text=True, capture_output=True
            )
            if result.stdout.strip():
                # Kill the process
                subprocess.run(
                    f'lsof -ti:{port} | xargs kill -9',
                    shell=True
                )
                print(f"Killed process that was using port {port}")
    except Exception as e:
        print(f"Warning: Failed to kill process on port {port}: {e}")
        # Continue anyway

def main():
    parser = argparse.ArgumentParser(description="Start the MCP Test UI server")
    parser.add_argument(
        "--server", "-s",
        help="Path to the MCP server file (default: ./src/server.py)",
        default=os.path.join(os.path.dirname(__file__), "src", "server.py")
    )
    parser.add_argument(
        "--host", "-H",
        help="Host address to bind the server to (default: 127.0.0.1)",
        default="127.0.0.1"
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        help="Port to run the server on (default: 8000)",
        default=8000
    )
    
    args = parser.parse_args()
    
    # Verify the server file exists
    if not os.path.exists(args.server):
        print(f"Error: MCP server file not found at {args.server}")
        sys.exit(1)
    
    # Kill any process already using the specified port
    kill_process_on_port(args.port)
    
    print(f"Starting MCP Test UI server at http://{args.host}:{args.port}")
    print(f"Using MCP server: {args.server}")
    print("Press Ctrl+C to stop the server")
    
    # Run the server
    run_server(args.server, args.host, args.port)

if __name__ == "__main__":
    main()
