
echo "Killing any existing FastMCP inspector processes..."
lsof -ti :6277 | xargs kill -9
lsof -ti :6274 | xargs   kill -9

echo "Starting FastMCP inspector..."
npx @modelcontextprotocol/inspector 
# /Users/petetreadaway/Projects/ebay-mcp-server/.venv/bin/python /Users/petetreadaway/Projects/ebay-mcp-server/src/main_server.py

# Direct Start
# http://127.0.0.1:6274/?transport=stdio&serverCommand=/Users/petetreadaway/Projects/ebay-mcp-server/.venv/bin/python&serverArgs=/Users/petetreadaway/Projects/ebay-mcp-server/src/main_server.py#tools
