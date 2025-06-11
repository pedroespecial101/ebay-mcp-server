#!/usr/bin/env python3
"""
Test script for the create_or_replace_inventory_item MCP tool
"""
import json
import requests
import time

# Test data for creating an inventory item (minimal test)
test_inventory_item = {
    "sku": "TEST-HEADER-FIX-001",
    "condition": "NEW",
    "product_title": "Test Product - Header Fix Test",
    "product_description": "Testing the Content-Language header fix for the create_or_replace_inventory_item tool.",
    "quantity": 1
}

def test_create_inventory_item():
    """Test creating an inventory item via the MCP Test UI API"""

    # MCP Test UI endpoint - note the tool name includes the server prefix
    url = "http://127.0.0.1:8000/mcp/execute/inventoryAPI_create_or_replace_inventory_item"
    
    print("Testing create_or_replace_inventory_item MCP tool...")
    print(f"URL: {url}")
    print(f"Test data: {json.dumps(test_inventory_item, indent=2)}")
    print("-" * 60)
    
    try:
        # Make the request
        response = requests.post(url, json=test_inventory_item, timeout=30)
        
        print(f"Response Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print("-" * 60)
        
        if response.status_code == 200:
            try:
                result = response.json()
                print("Response JSON:")
                print(json.dumps(result, indent=2))
                
                # Check if the result contains success information
                if isinstance(result, dict) and 'result' in result:
                    tool_result = json.loads(result['result'])
                    if tool_result.get('success'):
                        print("\n✅ SUCCESS: Inventory item created/updated successfully!")
                        print(f"SKU: {tool_result.get('sku')}")
                        print(f"Operation: {tool_result.get('operation')}")
                        print(f"Status Code: {tool_result.get('status_code')}")
                    else:
                        print("\n❌ FAILED: Tool execution failed")
                        print(f"Error: {tool_result.get('message')}")
                else:
                    print("\n⚠️  Unexpected response format")
                    
            except json.JSONDecodeError as e:
                print(f"Failed to parse JSON response: {e}")
                print(f"Raw response: {response.text}")
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            print(f"Response: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

def test_update_inventory_item():
    """Test updating the same inventory item (should get 204 status)"""
    
    # Modify some fields for the update test
    update_data = test_inventory_item.copy()
    update_data["quantity"] = 10
    update_data["product_description"] = "Updated description: High-quality wireless Bluetooth headphones with enhanced noise cancellation."
    update_data["condition_description"] = "Brand new in original packaging - Updated"
    
    url = "http://127.0.0.1:8000/mcp/execute/inventoryAPI_create_or_replace_inventory_item"
    
    print("\n" + "=" * 60)
    print("Testing UPDATE operation (same SKU)...")
    print(f"URL: {url}")
    print(f"Updated fields: quantity={update_data['quantity']}")
    print("-" * 60)
    
    try:
        response = requests.post(url, json=update_data, timeout=30)
        
        print(f"Response Status Code: {response.status_code}")
        print("-" * 60)
        
        if response.status_code == 200:
            try:
                result = response.json()
                print("Response JSON:")
                print(json.dumps(result, indent=2))
                
                if isinstance(result, dict) and 'result' in result:
                    tool_result = json.loads(result['result'])
                    if tool_result.get('success'):
                        print("\n✅ SUCCESS: Inventory item updated successfully!")
                        print(f"SKU: {tool_result.get('sku')}")
                        print(f"Operation: {tool_result.get('operation')}")
                        print(f"Status Code: {tool_result.get('status_code')}")
                    else:
                        print("\n❌ FAILED: Tool execution failed")
                        print(f"Error: {tool_result.get('message')}")
                        
            except json.JSONDecodeError as e:
                print(f"Failed to parse JSON response: {e}")
                print(f"Raw response: {response.text}")
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            print(f"Response: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    print("🧪 Testing create_or_replace_inventory_item MCP Tool")
    print("=" * 60)
    
    # Test creating a new inventory item
    test_create_inventory_item()
    
    # Wait a bit between tests
    time.sleep(2)
    
    # Test updating the same inventory item
    test_update_inventory_item()
    
    print("\n" + "=" * 60)
    print("🏁 Test completed!")
    print("Check the MCP Test UI at http://127.0.0.1:8000/mcp/ for manual testing")
