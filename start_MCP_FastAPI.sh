#!/bin/bash

# Script to set up and start the MCP FastAPI server
PROJECT_ROOT=$(dirname "$(realpath "$0")")
VENV_DIR="$PROJECT_ROOT/.venv"

echo "Setting up MCP FastAPI server..."

# Ensure no FastAPI server instances are running
pkill -f "uvicorn src.fastapi_integration:app"

# Check if virtual environment exists, create it if not
if [ ! -d "$VENV_DIR" ]; then
  echo "Virtual environment not found. Creating new virtual environment..."
  python3 -m venv "$VENV_DIR"
  
  echo "Installing dependencies..."
  source "$VENV_DIR/bin/activate"
  pip install --upgrade pip
  pip install -r "$PROJECT_ROOT/requirements.txt"
else
  echo "Using existing virtual environment..."
  source "$VENV_DIR/bin/activate"
fi

# Ensure dependencies are up to date
echo "Checking for dependency updates..."
pip install -r "$PROJECT_ROOT/requirements.txt"

# Set Python path to include project root
echo "Setting PYTHONPATH to include project root..."
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

# Start the FastAPI server
echo "Starting FastAPI server..."
cd "$PROJECT_ROOT"
uvicorn src.fastapi_integration:app --host 0.0.0.0 --port 8001 --reload

# Note: The server will continue to run until you press CTRL+C
