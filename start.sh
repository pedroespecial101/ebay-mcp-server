#!/bin/bash

# Configuration
SERVER_PID_FILE="fastmcp_server.pid"
LOG_FILE="fastmcp_server.log"
VENV_PATH=".venv/bin/activate"
SERVER_SCRIPT="src/server.py"

# Function to start the server
start_server() {
    echo "Starting FastMCP server..."
    # Activate virtual environment
    source "$VENV_PATH"
    # Run server with stdio transport, save PID, and redirect output to log file
    nohup python "$SERVER_SCRIPT" > "$LOG_FILE" 2>&1 & echo $! > "$SERVER_PID_FILE"
    echo "Server started with PID $(cat $SERVER_PID_FILE)"
    echo "Logs are being written to $LOG_FILE"
    echo "Server is running with stdio transport. Use an MCP client to interact with it."
}

# Function to stop the server
stop_server() {
    if [ -f "$SERVER_PID_FILE" ]; then
        PID=$(cat "$SERVER_PID_FILE")
        echo "Stopping FastMCP server (PID: $PID)..."
        kill -TERM "$PID"
        rm -f "$SERVER_PID_FILE"
        echo "Server stopped"
    else
        echo "No server PID file found. Is the server running?"
    fi
}

# Function to restart the server
restart_server() {
    stop_server
    sleep 2
    start_server
}

# Function to check server status
status_server() {
    if [ -f "$SERVER_PID_FILE" ]; then
        PID=$(cat "$SERVER_PID_FILE")
        if ps -p "$PID" > /dev/null; then
            echo "FastMCP server is running with PID: $PID"
            return 0
        else
            echo "PID file exists but server is not running"
            return 1
        fi
    else
        echo "FastMCP server is not running"
        return 1
    fi
}

# Main script logic
case "$1" in
    start)
        start_server
        ;;
    stop)
        stop_server
        ;;
    restart)
        restart_server
        ;;
    status)
        status_server
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac

exit 0
