import asyncio
import json
from fastmcp import Client

async def main():
    # Connect via stdio to a local script
    async with Client("src/main_server.py") as client:
        # Define the inventory item to delete
        delete_item_data = {
            "sku": "TT-01",
            "action": "delete"
        }

        # Call the manage_inventory_item tool to delete the item
        result = await client.call_tool(
            "inventoryAPI_manage_inventory_item",
            {
                "params": delete_item_data
            }
        )
        
        # Extract the text content and parse JSON
        try:
            # Get the first TextContent object and parse its text as JSON
            json_data = json.loads(result[0].text)
            # Pretty print the JSON with indentation
            print("Result:")
            print(json.dumps(json_data, indent=2))
        except (IndexError, json.JSONDecodeError) as e:
            print(f"Error formatting result: {e}")
            print("Raw result:", result)

if __name__ == "__main__":
    asyncio.run(main())
