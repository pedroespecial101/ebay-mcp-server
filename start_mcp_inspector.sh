
echo "Killing any existing FastMCP inspector processes..."
lsof -ti :6277 | xargs kill -9
lsof -ti :6274 | xargs   kill -9

echo "Starting eBayAPI-MCP-Server inspector..."
npx @modelcontextprotocol/inspector --config /Users/petetreadaway/Projects/ebay-mcp-server/MCP_Inspector_Config.json --server ebayAPI-mcp-server

