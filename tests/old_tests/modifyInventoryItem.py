import asyncio
import json
from fastmcp import Client

async def main():
    # Connect via stdio to a local script
    async with Client("src/main_server.py") as client:
        # Define the inventory item data
        inventory_item_data = {
            "sku": "TT-01",
            "action": "modify",
            "item_data": {
                "product": {
                    "sku": "TT-01",
                    "title": "Copeland Spode Queen Elizabeth II 1953 Coronation Cup and Saucer - MODIFIED",
                    "description": "MODIFIED: This is a Copeland Spode cup and saucer commemorating the coronation of Queen Elizabeth II on June 2nd, 1953. The mug has a creamy white glaze with brown transfer printing and coloured crests. It features a portrait of Queen Elizabeth II, the royal crest, and text marking the occasion.",
                    "imageUrls": [
                        "https://eBayImages.s3.us-east-005.backblazeb2.com/ebay_images/Cup-2/Cup-2-1_81.jpg",
                        "https://eBayImages.s3.us-east-005.backblazeb2.com/ebay_images/Cup-2/Cup-2-1_78.jpg",
                        "https://eBayImages.s3.us-east-005.backblazeb2.com/ebay_images/Cup-2/Cup-2-1_80.jpg",
                        "https://eBayImages.s3.us-east-005.backblazeb2.com/ebay_images/Cup-2/Cup-2-1_82.jpg",
                        "https://eBayImages.s3.us-east-005.backblazeb2.com/ebay_images/Cup-2/Cup-2-1_79.jpg",
                        "https://eBayImages.s3.us-east-005.backblazeb2.com/ebay_images/Cup-2/Cup-2-1_77.jpg"
                    ]
                },
                "condition": "USED_EXCELLENT",
                "conditionDescription": "MODIFIED: Used condition with staining and minor chips around the rims. The glaze is crazed and discolored. There are marks and scuffs on the exterior surface.",
                "availability": {
                    "shipToLocationAvailability": {
                        "quantity": 1
                    }
                }
            }
        }

        # Call the manage_inventory_item tool with the inventory item data
        result = await client.call_tool(
            "inventoryAPI_manage_inventory_item",
            {
                "params": inventory_item_data
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
