import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from fastmcp import Client

# Configure logging
log_dir = Path(__file__).parent / "test_logs"
log_dir.mkdir(exist_ok=True)
log_file = log_dir / f"{Path(__file__).stem}-{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# Create formatters
console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

# Configure root logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# File handler
file_handler = logging.FileHandler(log_file)
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

logger.info(f"Logging to file: {log_file}")

# Test configuration
TEST_SKU = "TT-01"  # Replace with a test SKU that exists in your inventory
TEST_CATEGORY_ID = "39630"  # Test category ID

class TestResult:
    def __init__(self, name):
        self.name = name
        self.passed = False
        self.error = None
        self.details = None

    def set_passed(self, details=None):
        self.passed = True
        self.error = None
        self.details = details
        return self

    def set_failed(self, error, details=None):
        self.passed = False
        self.error = str(error)
        self.details = details
        return self

    def __str__(self):
        status = "PASSED" if self.passed else f"FAILED: {self.error}"
        details = f"\n    Details: {self.details}" if self.details else ""
        return f"{self.name}: {status}{details}"

async def manage_offer_test():
    test_results = []
    
    # Connect to the MCP server via stdio
    try:
        async with Client("src/main_server.py") as client:
            logger.info("Connected to MCP server")
            
            # First, check if the offer already exists
            test_check = TestResult("Check Existing Offer")
            logger.info("Checking if offer already exists...")
            offer_id = None
            
            try:
                # Try to get the existing offer
                get_result = await client.call_tool(
                    "inventoryAPI_manage_offer",
                    {
                        "params": {
                            "sku": TEST_SKU,
                            "action": "get"
                        }
                    }
                )
                
                try:
                    json_data = json.loads(get_result[0].text)
                    if json_data.get('success') and 'data' in json_data and 'offer_id' in json_data['data']:
                        offer_id = json_data['data']['offer_id']
                        test_check.set_passed(f"Found existing offer with ID: {offer_id}")
                        logger.info(f"Using existing offer ID: {offer_id}")
                    else:
                        test_check.set_failed("No existing offer found", json_data)
                except (IndexError, json.JSONDecodeError) as e:
                    error_msg = f"Error parsing get result: {e}"
                    test_check.set_failed(error_msg, str(get_result))
                    raise
                
            except Exception as e:
                error_msg = f"Error checking for existing offer: {str(e)}"
                logger.error(error_msg, exc_info=True)
                test_check.set_failed(error_msg)
            
            test_results.append(test_check)
            logger.info(str(test_check))
            
            # If no existing offer, create a new one
            if not offer_id:
                test_create = TestResult("Create Offer")
                logger.info("No existing offer found, creating a new one...")
                
                try:
                    create_result = await client.call_tool(
                        "inventoryAPI_manage_offer",
                        {
                            "params": {
                                "sku": TEST_SKU,
                                "action": "create",
                                "offer_data": {
                                    "categoryId": TEST_CATEGORY_ID,
                                    "availableQuantity": 1,
                                    "pricingSummary": {
                                        "price": {
                                            "value": "9.99",
                                            "currency": "GBP"
                                        }
                                    },
                                    "listingDescription": "Test listing description"
                                }
                            }
                        }
                    )
                    
                    try:
                        json_data = json.loads(create_result[0].text)
                        logger.info("Create offer result:")
                        logger.info(json.dumps(json_data, indent=2))
                        if json_data.get('success') and 'offer_id' in json_data.get('data', {}):
                            test_create.set_passed(f"Created offer with ID: {json_data['data']['offer_id']}")
                            offer_id = json_data['data']['offer_id']
                        else:
                            error_msg = json_data.get('error', 'Unknown error')
                            test_create.set_failed(f"Failed to create offer: {error_msg}")
                    except (IndexError, json.JSONDecodeError) as e:
                        error_msg = f"Error formatting create result: {e}"
                        logger.error(error_msg)
                        logger.error(f"Raw result: {create_result}")
                        test_create.set_failed(error_msg, str(create_result))
                        raise
                    
                    test_results.append(test_create)
                    logger.info(str(test_create))
                    
                    if not test_create.passed:
                        logger.error("Skipping remaining tests due to create offer failure")
                        return test_results
                        
                except Exception as e:
                    error_msg = f"Error in create offer: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    test_create.set_failed(error_msg)
                    test_results.append(test_create)
                    return test_results
            
            # If we reach here, we either found an existing offer or successfully created a new one
            
            # Test getting the offer
            test_get = TestResult("Get Offer")
            logger.info("Testing get offer...")
            try:
                get_result = await client.call_tool(
                    "inventoryAPI_manage_offer",
                    {
                        "params": {
                            "sku": TEST_SKU,
                            "action": "get"
                        }
                    }
                )
                
                try:
                    json_data = json.loads(get_result[0].text)
                    logger.info("Get offer result:")
                    logger.info(json.dumps(json_data, indent=2))
                    if json_data.get('success') and 'data' in json_data and json_data['data'].get('offer_id') == offer_id:
                        test_get.set_passed(f"Successfully retrieved offer {offer_id}")
                    else:
                        test_get.set_failed("Failed to get offer", json_data)
                except (IndexError, json.JSONDecodeError) as e:
                    error_msg = f"Error formatting get result: {e}"
                    logger.error(error_msg)
                    logger.error(f"Raw result: {get_result}")
                    test_get.set_failed(error_msg, str(get_result))
                    raise
            except Exception as e:
                error_msg = f"Error in get offer test: {str(e)}"
                logger.error(error_msg, exc_info=True)
                test_get.set_failed(error_msg)
                raise
            finally:
                test_results.append(test_get)
                logger.info(str(test_get))
            
            # Test modifying the offer
            test_modify = TestResult("Modify Offer")
            logger.info("Testing modify offer...")
            
            try:
                modify_result = await client.call_tool(
                    "inventoryAPI_manage_offer",
                    {
                        "params": {
                            "sku": TEST_SKU,
                            "action": "modify",
                            "offer_data": {
                                "availableQuantity": 2,
                                "pricingSummary": {
                                    "price": {
                                        "value": "19.99",
                                        "currency": "GBP"
                                    }
                                },
                                "condition": "USED_EXCELLENT"  # Add required condition field
                            }
                        }
                    }
                )
                
                # Handle the response
                try:
                    # First try to parse as JSON
                    try:
                        json_data = json.loads(modify_result[0].text)
                        logger.info("Modify offer result (JSON):")
                        logger.info(json.dumps(json_data, indent=2))
                        
                        if json_data.get('success') and 'data' in json_data and json_data['data'].get('offer_id') == offer_id:
                            test_modify.set_passed(f"Successfully modified offer {offer_id}")
                        else:
                            error_msg = json_data.get('error', 'Unknown error')
                            test_modify.set_failed(f"Failed to modify offer: {error_msg}", json_data)
                            
                    except json.JSONDecodeError:
                        # If not JSON, log the raw text
                        logger.info("Modify offer result (raw text):")
                        logger.info(modify_result[0].text)
                        
                        # Check for common error patterns in the text
                        if "error" in modify_result[0].text.lower():
                            test_modify.set_failed(f"Modify failed with error: {modify_result[0].text}")
                        else:
                            test_modify.set_failed(f"Unexpected response format: {modify_result[0].text}")
                        
                except (IndexError, AttributeError) as e:
                    error_msg = f"Error processing modify result: {e}"
                    logger.error(error_msg)
                    logger.error(f"Raw result: {modify_result}")
                    test_modify.set_failed(error_msg, str(modify_result))
                    
            except Exception as e:
                error_msg = f"Error in modify offer test: {str(e)}"
                logger.error(error_msg, exc_info=True)
                test_modify.set_failed(error_msg)
                
            finally:
                test_results.append(test_modify)
                logger.info(str(test_modify))
                
                # Log a warning about the modify error but don't fail the entire test
                if not test_modify.passed:
                    logger.warning("Modify offer test failed, but continuing with remaining tests...")
            
            # Test publishing the offer
            test_publish = TestResult("Publish Offer")
            logger.info("Testing publish offer...")
            
            try:
                # First, update the offer with required condition information
                update_result = await client.call_tool(
                    "inventoryAPI_manage_offer",
                    {
                        "params": {
                            "sku": TEST_SKU,
                            "action": "modify",
                            "offer_data": {
                                "availableQuantity": 2,
                                "pricingSummary": {
                                    "price": {
                                        "value": "19.99",
                                        "currency": "GBP"
                                    }
                                },
                                "condition": "USED_EXCELLENT",
                                "conditionDescription": "Chips around edge",
                                "categoryId": TEST_CATEGORY_ID,
                            }
                        }
                    }
                )
                
                # Now try to publish the offer
                publish_result = await client.call_tool(
                    "inventoryAPI_manage_offer",
                    {
                        "params": {
                            "sku": TEST_SKU,
                            "action": "publish"
                        }
                    }
                )
                
                try:
                    # First try to parse as JSON
                    try:
                        json_data = json.loads(publish_result[0].text)
                        logger.info("Publish offer result (JSON):")
                        logger.info(json.dumps(json_data, indent=2))
                        
                        if json_data.get('success') and 'data' in json_data and 'listingId' in json_data['data'].get('details', {}):
                            test_publish.set_passed(f"Successfully published offer as listing {json_data['data']['details']['listingId']}")
                        else:
                            error_msg = json_data.get('error', 'Unknown error')
                            test_publish.set_failed(f"Failed to publish offer: {error_msg}")
                            
                    except json.JSONDecodeError:
                        # If not JSON, log the raw text
                        logger.info("Publish offer result (raw text):")
                        logger.info(publish_result[0].text)
                        
                        # Check for common error patterns in the text
                        if "error" in publish_result[0].text.lower():
                            test_publish.set_failed(f"Publish failed with error: {publish_result[0].text}")
                        else:
                            test_publish.set_failed(f"Unexpected response format: {publish_result[0].text}")
                        
                except (IndexError, AttributeError) as e:
                    error_msg = f"Error processing publish result: {e}"
                    logger.error(error_msg)
                    logger.error(f"Raw result: {publish_result}")
                    test_publish.set_failed(error_msg, str(publish_result))
                    
            except Exception as e:
                error_msg = f"Error in publish offer test: {str(e)}"
                logger.error(error_msg, exc_info=True)
                test_publish.set_failed(error_msg)
                
            finally:
                test_results.append(test_publish)
                logger.info(str(test_publish))
                
                # Log a warning about the publish error but don't fail the entire test
                if not test_publish.passed:
                    logger.warning("Publish offer test failed, but continuing with remaining tests...")

            # Test withdrawing the offer
            test_withdraw = TestResult("Withdraw Offer")
            logger.info("Testing withdraw offer...")
            try:
                withdraw_result = await client.call_tool(
                    "inventoryAPI_manage_offer",
                    {
                        "params": {
                            "sku": TEST_SKU,
                            "action": "withdraw"
                        }
                    }
                )
                
                try:
                    json_data = json.loads(withdraw_result[0].text)
                    logger.info("Withdraw offer result:")
                    logger.info(json.dumps(json_data, indent=2))
                    if json_data.get('success') and 'data' in json_data and json_data['data'].get('offer_id') == offer_id:
                        test_withdraw.set_passed(f"Successfully withdrew offer {offer_id}")
                    else:
                        test_withdraw.set_failed("Failed to withdraw offer", json_data)
                except (IndexError, json.JSONDecodeError) as e:
                    error_msg = f"Error formatting withdraw result: {e}"
                    logger.error(error_msg)
                    logger.error(f"Raw result: {withdraw_result}")
                    test_withdraw.set_failed(error_msg, str(withdraw_result))
                    raise
            except Exception as e:
                error_msg = f"Error in withdraw offer test: {str(e)}"
                logger.error(error_msg, exc_info=True)
                test_withdraw.set_failed(error_msg)
                raise
            finally:
                test_results.append(test_withdraw)
                logger.info(str(test_withdraw))
                
                # Print test summary
                logger.info("\n" + "="*50)
                logger.info("TEST SUMMARY")
                logger.info("="*50)
                
                passed = sum(1 for r in test_results if r.passed)
                total = len(test_results)
                
                for result in test_results:
                    logger.info(str(result))
                
                logger.info("\n" + "-"*50)
                logger.info(f"TOTAL: {passed} out of {total} tests passed ({passed/total*100:.1f}%)")
                logger.info("="*50 + "\n")
    
    except Exception as e:
        logger.error(f"Error during test: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    asyncio.run(manage_offer_test())
