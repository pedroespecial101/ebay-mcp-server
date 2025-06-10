
print "Killing any existing FastMCP inspector processes..."
lsof -ti :6277 | xargs kill -9
lsof -ti :6274 | xargs   kill -9

echo "Starting FastMCP inspector..."
npx @modelcontextprotocol/inspector python /Users/petetreadaway/Projects/ebay-mcp-server/src/main_server.py

