#!/bin/bash

# Script to start the MCP Test UI server

# Ensure the script is run from the project root
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
if [ "$PWD" != "$SCRIPT_DIR" ]; then
  echo "Please run this script from the project root directory: $SCRIPT_DIR"
  cd "$SCRIPT_DIR" || exit 1
fi

# Function to check and start Cloudflare tunnel
check_and_start_cloudflare_tunnel() {
  TUNNEL_NAME="dev-tunnel"
  TUNNEL_LOG_FILE="cloudflare_tunnel_${TUNNEL_NAME}.log"
  echo "-----------------------------------------------------"
  echo "Checking Cloudflare tunnel '$TUNNEL_NAME' status..."

  if ! command -v cloudflared &> /dev/null; then
    echo "Error: 'cloudflared' command not found. Please install Cloudflare Tunnel."
    echo "Skipping tunnel check."
    echo "-----------------------------------------------------"
    return 1
  fi

  local cloudflared_cmd_prefix=""
  if command -v timeout &> /dev/null; then
    cloudflared_cmd_prefix="timeout 10s"
  else
    echo "Info: 'timeout' command not found. 'cloudflared tunnel info' will run without a timeout."
    echo "      This might cause the script to hang if 'cloudflared' is unresponsive."
    echo "      Consider installing 'coreutils' (e.g., 'brew install coreutils' on macOS)."
  fi

  echo "Executing: $cloudflared_cmd_prefix cloudflared tunnel info \"$TUNNEL_NAME\""
  # SC2086 is intentionally ignored here because cloudflared_cmd_prefix is either empty or 'timeout 10s'
  # shellcheck disable=SC2086
  tunnel_info_output=$($cloudflared_cmd_prefix cloudflared tunnel info "$TUNNEL_NAME" 2>&1)
  tunnel_info_exit_code=$?

  if echo "$tunnel_info_output" | grep -q "does not have any active connection"; then
    echo "Cloudflare tunnel '$TUNNEL_NAME' is not running."
    echo "Starting it now in the background (logs to $TUNNEL_LOG_FILE)..."
    nohup cloudflared tunnel run "$TUNNEL_NAME" > "$TUNNEL_LOG_FILE" 2>&1 &
    TUNNEL_PID=$!
    echo "Tunnel process started with PID $TUNNEL_PID."
    
    echo "Waiting a few seconds for tunnel to establish connection..."
    sleep 5

    echo "Re-checking tunnel status with: $cloudflared_cmd_prefix cloudflared tunnel info \"$TUNNEL_NAME\""
    # SC2086 is intentionally ignored here
    # shellcheck disable=SC2086
    tunnel_info_output_after_start=$($cloudflared_cmd_prefix cloudflared tunnel info "$TUNNEL_NAME" 2>&1)
    if echo "$tunnel_info_output_after_start" | grep -q "does not have any active connection"; then
        echo "Warning: Cloudflare tunnel '$TUNNEL_NAME' may not have started correctly or is taking too long."
        echo "Please check '$TUNNEL_LOG_FILE' and run 'cloudflared tunnel info $TUNNEL_NAME' manually."
    else
        echo "Cloudflare tunnel '$TUNNEL_NAME' appears to be active now."
    fi
  elif [ $tunnel_info_exit_code -eq 0 ] && echo "$tunnel_info_output" | grep -q "ID:" && echo "$tunnel_info_output" | grep -q "CONNECTOR ID"; then
    echo "Cloudflare tunnel '$TUNNEL_NAME' is already running and active."
  else
    echo "Could not determine Cloudflare tunnel '$TUNNEL_NAME' status or an error occurred."
    echo "Output from 'cloudflared tunnel info $TUNNEL_NAME' (exit code $tunnel_info_exit_code):"
    echo "$tunnel_info_output"
    echo "If the tunnel should be running, please check its configuration and logs."
  fi
  echo "-----------------------------------------------------"
  echo # Add a newline for better readability
}

# Activate virtual environment
if [ -d ".venv" ]; then
  echo "Activating virtual environment..."
  source .venv/bin/activate
else
  echo "Error: Virtual environment '.venv' not found. Please set it up first."
  exit 1
fi

# Check and start Cloudflare tunnel if not running
check_and_start_cloudflare_tunnel

PORT=8000

# Kill any process already using the port
echo "Checking for existing processes on port $PORT..."
if lsof -ti:$PORT > /dev/null ; then
  echo "Killing existing process(es) on port $PORT..."
  lsof -ti:$PORT | xargs kill -9
else
  echo "No existing processes found on port $PORT."
fi

# Start the MCP Test UI server with auto-reload
echo "Starting MCP Test UI server on http://127.0.0.1:$PORT with auto-reload"
echo "MCP tools will be available under /mcp/ (e.g., http://127.0.0.1:$PORT/mcp/)"
uvicorn mcp_test_ui.app:app --host 127.0.0.1 --port $PORT --reload

# Deactivate virtual environment upon script exit (optional, usually handled by shell)
# deactivate
