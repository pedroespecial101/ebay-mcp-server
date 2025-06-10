Be concise. Create an all-in-one eBay offer management MCP tool following the existing project patterns.

## Task
Create a single MCP tool that handles Create, Modify, Withdraw, and Publish operations for eBay offers based on inventory item SKU. This consolidates what would normally be 4 separate eBay API calls into one semantic tool.

## Requirements
1. Follow the exact patterns from `src/ebay_mcp/inventory/get_inventory_item_by_sku.py`
2. Use Pydantic schemas for validation
3. Create separate .py file in appropriate directory structure
4. Use existing utils: `execute_ebay_api_call`, `get_standard_ebay_headers`, `create_debug_client`
5. Follow the async/await patterns and logging structure
6. Import models from the models directory structure

## Tool Specification
- **Tool name**: `manage_offer`
- **Parameters**: 
  - `sku` (required): Inventory item SKU
  - `action` (required): "create" | "modify" | "withdraw" | "publish"
  - `offer_details` (conditional): Required for create/modify, contains pricing, quantity, etc.
 --- Note that the Modify offer should perform a Get Offer first and repopulate all unchanged fields as eBay's API is a COMPLETE replace operation
## Implementation Notes
- Use action parameter to determine which eBay API endpoint to call
- Create appropriate Pydantic models for request/response validation
- Handle different parameter requirements per action type
- Map to correct eBay offer management endpoints
- Maintain same error handling and response patterns as example
- The main entry point for this MCP server is at src/main_server.py then sub-servers are used.

Examine the existing codebase structure and the provided example file to understand the patterns, then implement this consolidated offer management tool.

## Folder Structure for /src (main MCP stuff)
src/
├── ebay_mcp/
│   ├── auth/
│   │   └── server.py
│   ├── browse/
│   │   └── server.py
│   ├── identity/
│   ├── inventory/
│   │   ├── create_or_replace_inventory_item.py
│   │   ├── delete_inventory_item.py
│   │   ├── get_inventory_item_by_sku.py
│   │   ├── get_inventory_items.py
│   │   ├── listing_fees.py
│   │   ├── server.py
│   │   ├── update_offer.py
│   │   └── withdraw_offer.py
│   └── taxonomy/
│       └── server.py
├── ebay_service.py
├── main_server.py
├── models/
│   ├── auth.py
│   ├── base.py
│   ├── config/
│   │   └── settings.py
│   ├── ebay/
│   │   ├── browse.py
│   │   ├── inventory.py
│   │   └── taxonomy.py
│   └── mcp_tools.py
├── other_tools_mcp/
│   ├── database/
│   │   └── server.py
│   └── tests/
│       └── server.py
└── utils/
    ├── api_utils.py
    └── debug_httpx.py
 