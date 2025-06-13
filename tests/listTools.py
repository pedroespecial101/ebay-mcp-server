import asyncio
from fastmcp import Client
import json

async def main():
    # Connect via stdio to a local script
    async with Client("src/main_server.py") as client:
        tools = await client.list_tools()
        print(f"Available tools: {tools}")
        
        # Convert Tool objects to serializable dictionaries
        tools_data = [{
            'name': tool.name,
            'description': tool.description,
            'inputSchema': tool.inputSchema
        } for tool in tools]
        
        with open("tests/available_tools.json", "w") as f:
            json.dump(tools_data, f, indent=2)

        # result = await client.call_tool("add", {"a": 5, "b": 3})
        # print(f"Result: {result.text}")

if __name__ == "__main__":
    asyncio.run(main())