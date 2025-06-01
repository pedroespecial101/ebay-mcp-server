#!/bin/bash

# Script to start the MCP Test UI server

# Ensure the script is run from the project root
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
if [ "$PWD" != "$SCRIPT_DIR" ]; then
  echo "Please run this script from the project root directory: $SCRIPT_DIR"
  cd "$SCRIPT_DIR" || exit 1
fi

# Activate virtual environment
if [ -d ".venv" ]; then
  echo "Activating virtual environment..."
  source .venv/bin/activate
else
  echo "Error: Virtual environment '.venv' not found. Please set it up first."
  exit 1
fi

PORT=8000

# Kill any process already using the port
echo "Checking for existing processes on port $PORT..."
if lsof -ti:$PORT > /dev/null ; then
  echo "Killing existing process(es) on port $PORT..."
  lsof -ti:$PORT | xargs kill -9
else
  echo "No existing processes found on port $PORT."
fi

# Start the MCP Test UI server
echo "Starting MCP Test UI server on http://127.0.0.1:$PORT"
echo "MCP tools will be available under /mcp/ (e.g., http://127.0.0.1:$PORT/mcp/)"
python -m mcp_test_ui.app --host 127.0.0.1 --port $PORT

# Deactivate virtual environment upon script exit (optional, usually handled by shell)
# deactivate
