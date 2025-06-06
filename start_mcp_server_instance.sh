#!/bin/bash

# Configuration
LOG_FILE="logs/fastmcp_server.log" # Updated log file path
VENV_PATH=".venv/bin/activate"
SERVER_SCRIPT="src/main_server.py" # Updated to use the new main server with dynamic composition

echo "Ensuring no old FastMCP server instances are running..."
# Kill any existing server processes by matching the command line
# This is more robust than relying on a PID file.
pkill -f "fastmcp dev $SERVER_SCRIPT"

# Add a small delay to allow processes to terminate if needed
sleep 1



echo "Starting FastMCP server..."

# Activate virtual environment
if [ -f "$VENV_PATH" ]; then
    source "$VENV_PATH"
else
    echo "Error: Virtual environment not found at $VENV_PATH. Please ensure it's set up."
    exit 1
fi

echo "Unsetting EBAY_USER_REFRESH_TOKEN and EBAY_USER_ACCESS_TOKEN..."
unset EBAY_USER_REFRESH_TOKEN
unset EBAY_USER_ACCESS_TOKEN


# Create logs directory if it doesn't exist
mkdir -p "$(dirname "$LOG_FILE")"

# Clear the log file before starting to ensure fresh logs for error checking
echo "Clearing $LOG_FILE for fresh start..." > "$LOG_FILE"

# Run server with stdio transport, redirect output to log file
# nohup allows the server to keep running after the script exits
# '&' runs it in the background
nohup fastmcp dev "$SERVER_SCRIPT" >> "$LOG_FILE" 2>&1 &

# Get the PID of the last background process
SERVER_PID=$!

# Wait a moment for the server to potentially start or fail
sleep 2

# Check if the server process is actually running
if ps -p "$SERVER_PID" > /dev/null; then
    echo "Server started successfully with PID $SERVER_PID."
    echo "Logs are being written to $LOG_FILE"
    echo "Server is running with stdio transport. Use an MCP client to interact with it."
    echo ""
    echo "===== REMINDER: TESTING MODE ONLY ====="
    echo "This server instance is separate from your IDE's MCP integration."
    echo "Any code changes will require restarting this server using ./start.sh"
    echo "AND separately restarting your IDE's MCP integration for changes to take effect there."
    echo "========================================="
elif grep -q "Traceback (most recent call last):" "$LOG_FILE" || grep -q "Error:" "$LOG_FILE"; then
    echo "Server failed to start. An error was detected in the log file."
    echo "Last 10 lines of $LOG_FILE:"
    tail -n 10 "$LOG_FILE"
    exit 1
else
    echo "Server may have failed to start. PID $SERVER_PID is not running."
    echo "Please check $LOG_FILE for details."
    if [ -f "$LOG_FILE" ]; then
        echo "Last 10 lines of $LOG_FILE:"
        tail -n 10 "$LOG_FILE"
    fi
    exit 1
fi

exit 0
