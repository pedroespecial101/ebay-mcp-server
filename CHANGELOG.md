## Updates in TrajectoryID <filled_by_user_or_system>, (trajectoryID <filled_by_user_or_system>) - 15062025 - 11:16.21

- **User Modified:** `/Users/petetreadaway/Projects/ebay-mcp-server/tests/test_manageOffer_pytest.py`
  - Updated `TEST_SKU` and `TEST_CATEGORY_ID`.
  - Added `TEST_INVENTORY_ITEM_DATA`, `INITIAL_OFFER_DATA`, and `MODIFIED_OFFER_DATA` constants for test configuration.
  - Refined `_get_offer_details` helper function.
  - Significantly updated `test_01_cleanup_prepare_offer` to include inventory item creation if not exists, and more robust offer withdrawal logic.
  - Updated `test_02_create_offer`, `test_03_get_offer`, `test_04_modify_offer`, `test_05_publish_offer`, and `test_06_withdraw_offer` to use the new data constants and refined logic, including more specific assertions and print statements for progress.

## Updates in TrajectoryID <pydantic_model_refactor, (pydantic_model_refactor_14062025_1345)>, 14062025 - 13:45:35

- **Pydantic Model Refactoring (`src/models/ebay/inventory.py`)**:
  - Standardized all Pydantic model field names to `snake_case` for Python code, while using `alias_generator = to_camel` and `Field(alias=...)` to ensure `camelCase` JSON for eBay API compatibility.
  - Removed the unused `UpdateOfferRequest` Pydantic model to simplify the codebase.
  - Introduced a reusable `sku_field = Field(...)` for the common SKU attribute to improve maintainability and consistency.
- **Tool Implementation Updates for Model Refactor**:
  - Updated `src/ebay_mcp/inventory/manage_offer.py` and `src/ebay_mcp/inventory/manage_inventory_item.py` to use `model_dump(by_alias=True, exclude_none=True)` when preparing JSON payloads. This ensures that the `camelCase` aliases are correctly used for API communication.
  - Verified that `src/ebay_mcp/inventory/get_inventory_items.py` did not require changes due to its existing handling of response parsing.

## Updates in TrajectoryID <remove_unused_inventory_models, (remove_unused_inventory_models_14062025_1345)>, 14062025 - 13:45:35

- **Removed Unused Inventory Models**:
  - Deleted legacy Pydantic classes (`OfferPriceQuantity`, `OfferDetails`, `OfferRequest`, `OfferResponse`, `WithdrawOfferRequest`, `ListingFeeRequest`, `Fee`, `OfferFees`, `ListingFeeResponse`, `CreateOrReplaceInventoryItemResponse`).
  - Re-implemented `src/models/ebay/inventory.py` to include only actively used models: `UpdateOfferRequest`, `InventoryItemDetails`, and `InventoryItemsListResponse`.
- **Code Cleanup**: Removed stale comment reference to `WithdrawOfferRequest` in `src/ebay_mcp/inventory/manage_offer.py`.
- **Verification**: All tests pass (`pytest`).

## Updates in TrajectoryID <mark_unused_inventory_models, (mark_unused_inventory_models_14062025_1014)>, 14062025 - 10:14:00

- **Documentation Update**: Added usage comments to `src/models/ebay/inventory.py` for each class to indicate whether they are used elsewhere in the active codebase or appear unused.
- No functional code changes; comments only.

## Updates in TrajectoryID <convert_inventory_item_pytests, (convert_inventory_item_pytests)>, 13062025 - 17:59:53

- **Added Pytest Inventory Item Tests**:
  - Created `tests/test_manageInventoryItem_pytest.py` following the established pattern in `test_manageOffer_pytest.py`.
  - Includes tests for create, get, modify, and delete actions via `inventoryAPI_manage_inventory_item`.
  - Publish stage intentionally omitted as it is not applicable to inventory items.

## Updates in TrajectoryID <fix_fastmcp_instantiation, (1b2c3d4e)>, 12062025 - 18:29:46

- **Fix:** Corrected the instantiation of the `FastMCP` server in `src/ebay_mcp/prompts/server.py`.
- **Reason:** The `FastMCP` constructor was being called with incorrect keyword arguments. It only accepts a single positional string argument for the server's title. This was causing a `TypeError` on startup.
- **Change:** Modified the `FastMCP` call to use the correct signature: `prompts_mcp = FastMCP("Custom Prompts Server")`.

## Updates in TrajectoryID <refactor_default_offer_settings_to_config, (refactor_default_offer_settings_to_config)>, 12062025 - 18:19:12

- **Refactored Default Offer Settings**: Moved hardcoded default eBay offer values from business logic into a centralized Pydantic `BaseSettings` configuration.
  - Created `src/ebay_mcp/config.py` to define an `EbayOfferDefaults` class that loads settings from the `.env` file.
  - Updated the `create` action in `src/ebay_mcp/inventory/manage_offer.py` to use this configuration class.
  - The tool now applies these defaults automatically, while allowing user-provided values to override them, keeping the MCP tool interface clean and unchanged.

## Updates in TrajectoryID <add default eBay settings to .env, (add_ebay_settings)>, 12062025 - 17:50:39

- Added default eBay marketplace, listing, and tax settings to the `.env` file.

## Updates in TrajectoryID <remove_mcp_test_ui, (cascade_remove_mcp_test_ui)>, 12062025 - 08:39:30

- Removed legacy `mcp_test_ui/` directory and the `start_mcp_test_ui.sh` script.
- Overhauled `README.md` to eliminate references to the MCP Test UI and point users to MCP Inspector instead.
- Confirmed no production code in `src/` imports or relies on `mcp_test_ui`.
- No other breaking changes introduced.

## Updates in TrajectoryID <Remove Unused MCP Tools, (remove_unused_mcp_tools_11062025_1345)>, 11062025 - 13:45:00

- **Removed Unused MCP Tools**:
  - Removed the following MCP tools that were no longer needed:
    - `database_mock_db_query` - Test database query tool
    - `tests_add` - Simple addition test tool
    - `inventoryAPI_get_listing_fees` - Superseded by other tools
    - `inventoryAPI_get_offer_by_sku` - Functionality moved to manage_offer tool
  - Cleaned up related Pydantic models and request/response schemas
  - Updated `main_server.py` to remove mounting of test and database tools
  - Verified no remaining references to removed tools in the codebase

## Updates in TrajectoryID <Remove Deprecated Inventory Tools, (remove_deprecated_inventory_tools_11062025_1218)>, 11062025 - 12:18:00

- **Removed Deprecated Inventory Tools**:
  - Removed the following deprecated inventory management tools that have been superseded by the `manage_offer` tool:
    - `create_or_replace_inventory_item.py`
    - `get_inventory_item_by_sku.py`
    - `delete_inventory_item.py`
  - Removed related Pydantic models and request/response schemas
  - Updated `README.md` to remove references to the deleted tools
  - All inventory management should now be done through the consolidated `manage_offer` tool

## Updates in TrajectoryID <Update README for manage_offer.py, (cascade_update_readme_11062025_0949)>, 11062025 - 09:49:50

- **Updated `README.md` Documentation**:
    - Examined `src/ebay_mcp/inventory/manage_offer.py`.
    - Verified the `manage_offer` tool description in the "Inventory API Tools" section of `README.md`.
    - Ensured `manage_offer.py` is correctly listed in the "Project Structure" section in `README.md`.
    - Corrected a duplicated entry for the `manage_offer` tool in the "Inventory API Tools" section that was inadvertently added in a previous step.

## Updates in TrajectoryID <Add Verification to Offer Management, (cascade_update_06_11_2025_0801)>, 11062025 - 08:01:50

- **Enhanced `manage_offer` Tool with Verification Step**:
    - Added a verification step to the `CREATE` and `MODIFY` actions in the `manage_offer` tool in `src/ebay_mcp/inventory/manage_offer.py`.
    - After a successful `CREATE` or `MODIFY` operation, the tool now immediately performs a `GET` request to fetch the offer's latest state from eBay.
    - For `CREATE`, it confirms the offer was created and returns the full, verified payload.
    - For `MODIFY`, it compares the updated fields against the fetched data and reports any discrepancies.
    - The success response to the MCP client now includes the complete, verified offer payload from eBay in the `details` field, ensuring the client receives confirmation of the final state.
    - This change improves the reliability of the tool by confirming that eBay has successfully processed the changes before reporting success.

## Updates in TrajectoryID <Correct eBay API Field Naming in Manage Offer, (cascade_update_06_11_2025_0749)>, 11062025 - 07:49:21

- **Standardized eBay API Field Naming in `manage_offer.py`**:
    - Updated the `OfferDataForManage` Pydantic model in `src/ebay_mcp/inventory/manage_offer.py` to use `camelCase` field names (e.g., `categoryId` instead of `category_id`) to align with eBay API specifications.
    - Replaced existing field descriptions in `OfferDataForManage` with detailed descriptions sourced directly from the eBay Sell Inventory v1 API Overview (`EbayOfferDetailsWithAll` schema). This enhances the clarity and usability of the MCP tool's schema.
    - Added `class Config: allow_population_by_field_name = True` to `OfferDataForManage` to support population with `snake_case` keys while ensuring `camelCase` serialization.
    - Updated the `required_fields_create` list within the `manage_offer` tool's logic to use the new `camelCase` field names for validation of 'create' actions.
    - These changes ensure that JSON payloads sent to eBay use the correct field naming conventions and improve the descriptiveness of the MCP tool.

## Updates in TrajectoryID <Consolidate Offer Management Tools, (e1251790-8399-4501-a19c-51306f4424d3)>, 11062025 - 07:15:47

- **Enhanced `manage_offer` Tool**:
    - Added a new `get` action to the `manage_offer` tool in `src/ebay_mcp/inventory/manage_offer.py`.
    - This allows retrieving full offer details by SKU, with the output formatted like an `OfferDataForManage` payload for consistency.

- **Consolidated Offer Management**:
    - Removed the superseded `update_offer.py` and `withdraw_offer.py` tools.
    - Their functionality is now handled by the `modify` and `withdraw` actions within the single `manage_offer` tool.
    - Updated `src/ebay_mcp/inventory/server.py` to remove the registrations for the obsolete tools.
    - Deleted the corresponding files to clean up the codebase.

## Updates in TrajectoryID <Log Rotation Enhancement, (YOUR_CURRENT_TRAJECTORY_ID)>, 11062025 - 06:08:04

- **Enhanced Logging Rotation**:
    - Modified `src/main_server.py` to implement improved log file rotation.
    - The system now keeps the latest `fastmcp_server.log` and up to 9 backup files (10 total).
    - Backup files are named `fastmcp_server.log.NN_YYYY-MM-DD-HH:MM:SS`, where NN is the sequence number (01-09).
    - Replaced `logging.FileHandler` with `logging.handlers.RotatingFileHandler`.
    - Added a `custom_log_namer` function to handle the new filename format.
    - Commented out the old manual log archiving logic, as `RotatingFileHandler` now manages this.
    - Set log rotation to trigger when a log file reaches 10MB.

## Updates in TrajectoryID <pydantic_v2_migration_manage_offer_taxonomy_12062025_1410>, 12062025 - 14:10:00

- **Pydantic v2 Migration Progress**:
  - Replaced deprecated `root_validator` with `model_validator` in `src/ebay_mcp/inventory/manage_offer.py` (`ManageOfferToolInput`).
  - Updated import to use `model_validator` instead of `root_validator`.
  - Removed unused legacy Pydantic model imports (`CategorySuggestion*`, `ItemAspects*`) and heavy parsing logic from `src/ebay_mcp/taxonomy/server.py`. The server now relies on raw JSON responses with lightweight logging only, reducing maintenance overhead.
  - Confirmed inline models and shared models comply with Pydantic 2.0 standards in the modified files.

- **Next Steps**:
  - Run MCP Test UI and exercise `manage_offer` and taxonomy tools to ensure validation logic still works.
  - Continue auditing remaining modules for v2 compliance.

## Updates in TrajectoryID <remove_legacy_offer_param_models_12062025_1749>, 12062025 - 17:49:30

- **Removed Unused Legacy Models**:
  - Deleted `UpdateOfferParams` and `WithdrawOfferParams` classes from `src/models/mcp_tools.py` (legacy after tool consolidation).
  - Cleaned `src/ebay_mcp/inventory/server.py` to drop now-unused imports.
  - Confirmed no remaining references via codebase grep.

- **Housekeeping**:
  - Added comment placeholder in `mcp_tools.py` indicating models were removed during Pydantic v2 refactor.

## Updates in TrajectoryID <Fix Pydantic Serialization, (e1251790-8399-4501-a19c-51306f4424d3)>, 10062025 - 20:42:10

- **Fixed Pydantic Serialization**: Updated `src/ebay_mcp/inventory/manage_offer.py` to use `model_dump_json(indent=2)` instead of the deprecated `json(indent=2)` for serializing Pydantic model responses. This resolves a `TypeError` with Pydantic V2 and ensures correct JSON output formatting.

## Updates in TrajectoryID <Fix MCP Tool Signature for Schema Exposure, (e1251790-8399-4501-a19c-51306f4424d3)>, 10062025 - 20:29.28

- **Fixed `manage_offer` MCP Tool Signature**: Modified the `manage_offer` tool in `src/ebay_mcp/inventory/manage_offer.py` to correctly expose its schema to MCP clients.
  - Changed the tool signature to use Pydantic models directly (`ManageOfferAction` for `action` and `OfferDataForManage` for `offer_data`).
  - Introduced `ManageOfferToolInput` Pydantic model to encapsulate all input parameters (`sku`, `action`, `offer_data`) and their validation logic, including conditional requirements for `offer_data`.
  - The tool function `manage_offer` now accepts a single `params: ManageOfferToolInput` argument.
  - Removed manual instantiation and validation of `ManageOfferParams` from within the tool function, relying on FastMCP's automatic validation based on the Pydantic signature.
  - This ensures that MCP clients receive a complete JSON Schema for the tool, detailing all available fields, types, descriptions, and constraints for `offer_data`.

## Updates in TrajectoryID <Add AIO Offer MCP Tool, (e1251790-8399-4501-a19c-51306f4424d3)>, 10062025 - 19:10.11

- **Added `manage_offer` MCP Tool**: Introduced a new tool in `src/ebay_mcp/inventory/manage_offer.py`.
  - This tool consolidates eBay offer management operations (create, modify, withdraw, publish) into a single interface based on SKU.
  - Uses Pydantic models for request/response validation (`ManageOfferParams`, `OfferDataForManage`, `ManageOfferToolResponse`).
  - Follows existing project patterns for API calls, logging, and error handling.
  - Integrated into the inventory MCP server.

## Updates in TrajectoryID <inventory_item_limited_fields_11062025_1846>, 11062025 - 18:46:00

- **Refactored `InventoryItemDataForManage` model**:
  - Introduced strongly-typed nested models (`ProductDataForInventoryItem`, `AvailabilityData`, `ShipToLocationAvailability`) limited to the mandatory fields defined in `_archive/InventoryItemRequired_Limited.json`.
  - Added rich `Field` metadata (titles, descriptions, examples) sourced from *eBay Sell Inventory v1 API Overview* to improve MCP schema clarity.
  - Removed unused fields (`conditionDescriptors`, `packageWeightAndSize`) from the inventory item payload.
  - Updated validation logic in the `CREATE` action of `manage_inventory_item` to use the new nested models.

- **Documentation**:
  - Updated `README.md` to list the `manage_inventory_item` MCP tool with its new limited-field payload description.

## Updates in TrajectoryID <Comprehensive Update Offer Tool Enhancement, (05062025 - 06:40:00)>

### MAJOR ENHANCEMENT: Complete Update Offer Tool Overhaul

**CRITICAL WARNING ADDED**: The updateOffer API performs a COMPLETE REPLACEMENT operation. All current offer data will be overwritten with provided values. Any fields not included will be cleared/reset to defaults.

#### New Features Added:
1. **Complete Field Coverage**: Added support for ALL available eBay updateOffer API fields:
   - Core fields: `sku`, `marketplace_id`, `available_quantity` (existing)
   - Pricing: `pricing_summary` (replaces simple price parameter)
   - Categories: `category_id`, `secondary_category_id`
   - Listing content: `listing_description`, `listing_duration`, `listing_start_date`
   - Location/policies: `merchant_location_key`, `listing_policies`
   - Store integration: `store_category_names`
   - Purchase controls: `quantity_limit_per_buyer`, `lot_size`
   - Special features: `hide_buyer_details`, `include_catalog_product_details`
   - Compliance: `charity`, `extended_producer_responsibility`, `regulatory`, `tax`

2. **Enhanced Documentation**:
   - Comprehensive field descriptions with business logic constraints
   - Clear indication of required vs optional vs conditional fields
   - Examples and format specifications for complex fields
   - Prominent warnings about REPLACE operation behavior

3. **Robust Validation**:
   - Pydantic field validators for all constraints (SKU length ≤ 50, quantities ≥ 0, etc.)
   - Proper type checking and format validation
   - Array size limits (store categories ≤ 2, etc.)

4. **Backward Compatibility**:
   - Legacy `price` parameter automatically converted to `pricing_summary` format
   - Existing tool calls continue to work without modification

5. **Smart Data Preservation**:
   - Tool retrieves current offer data first
   - Preserves existing values for fields not specified in update
   - Prevents accidental data loss from incomplete requests

#### Technical Improvements:
- Updated `UpdateOfferParams` model with 21 comprehensive fields
- Enhanced `UpdateOfferRequest` model with full eBay API schema compliance
- Improved error handling and validation messages
- Better success reporting showing which fields were updated
- Comprehensive test suite covering all new functionality

#### Integration Guidance:
- **RECOMMENDED WORKFLOW**:
  1. Call Get Offer tool to retrieve current data
  2. Modify only desired fields while preserving others
  3. Include ALL existing values in update request
- Tool now supports both simple updates (price/quantity) and complex offer modifications
- Full support for published and unpublished offers with appropriate field requirements

#### Files Modified:
- `src/models/mcp_tools.py`: Complete UpdateOfferParams overhaul
- `src/models/ebay/inventory.py`: Enhanced UpdateOfferRequest model
- `src/ebay_mcp/inventory/update_offer.py`: Comprehensive tool implementation
- `tests/test_update_offer_comprehensive.py`: New comprehensive test suite

This update transforms the Update Offer tool from a basic price/quantity updater into a comprehensive offer management solution supporting all eBay Inventory API capabilities while maintaining safety through prominent warnings and data preservation features.
