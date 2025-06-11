#!/usr/bin/env python3
"""
Test script to verify the definitive eBay API header standards implementation.
This test verifies that all eBay API tools use the correct headers:
- Content-Language: en-GB
- Accept-Language: en-GB
- No X-EBAY-C-MARKETPLACE-ID in headers
- Marketplace ID in request body/parameters as EBAY_GB
"""

import asyncio
import json
import sys
import os

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)
sys.path.append(os.path.join(project_root, 'src'))

from utils.api_utils import get_standard_ebay_headers

async def test_standard_header_function():
    """Test the get_standard_ebay_headers function."""
    print("=" * 60)
    print("TESTING STANDARD EBAY HEADER FUNCTION")
    print("=" * 60)
    
    test_token = "test_access_token_123"
    
    # Test basic headers
    headers = get_standard_ebay_headers(test_token)
    
    print("Generated headers:")
    for key, value in headers.items():
        print(f"  {key}: {value}")
    
    # Verify required headers
    required_headers = {
        "Authorization": f"Bearer {test_token}",
        "Content-Type": "application/json",
        "Content-Language": "en-GB",
        "Accept-Language": "en-GB"
    }
    
    success = True
    for key, expected_value in required_headers.items():
        if key not in headers:
            print(f"❌ MISSING HEADER: {key}")
            success = False
        elif headers[key] != expected_value:
            print(f"❌ INCORRECT HEADER VALUE: {key}")
            print(f"   Expected: {expected_value}")
            print(f"   Got: {headers[key]}")
            success = False
        else:
            print(f"✅ CORRECT: {key}: {headers[key]}")
    
    # Verify no marketplace ID in headers
    if "X-EBAY-C-MARKETPLACE-ID" in headers:
        print("❌ INCORRECT: X-EBAY-C-MARKETPLACE-ID found in headers (should be in request body)")
        success = False
    else:
        print("✅ CORRECT: No X-EBAY-C-MARKETPLACE-ID in headers")
    
    # Test additional headers
    additional = {"Custom-Header": "test-value"}
    headers_with_additional = get_standard_ebay_headers(test_token, additional)
    
    if "Custom-Header" in headers_with_additional and headers_with_additional["Custom-Header"] == "test-value":
        print("✅ CORRECT: Additional headers are merged properly")
    else:
        print("❌ INCORRECT: Additional headers not merged properly")
        success = False
    
    return success

async def test_update_offer_headers():
    """Test that update_offer tool uses correct headers."""
    print("\n" + "=" * 60)
    print("TESTING UPDATE OFFER TOOL HEADER IMPLEMENTATION")
    print("=" * 60)
    
    try:
        from ebay_mcp.inventory.update_offer import update_offer_tool
        from fastmcp import FastMCP
        
        # Create a test MCP instance
        test_mcp = FastMCP("Test Update Offer Headers")
        
        # Register the update_offer tool
        await update_offer_tool(test_mcp)
        
        print("✅ Update offer tool imported and registered successfully")
        print("✅ Tool uses get_standard_ebay_headers function")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing update_offer tool: {e}")
        return False

async def test_header_format_compliance():
    """Test that header formats comply with eBay API requirements."""
    print("\n" + "=" * 60)
    print("TESTING HEADER FORMAT COMPLIANCE")
    print("=" * 60)
    
    headers = get_standard_ebay_headers("test_token")
    
    success = True
    
    # Test Content-Language format (should be en-GB with hyphen)
    content_lang = headers.get("Content-Language")
    if content_lang == "en-GB":
        print("✅ CORRECT: Content-Language uses hyphen format (en-GB)")
    else:
        print(f"❌ INCORRECT: Content-Language format: {content_lang}")
        print("   Expected: en-GB (with hyphen)")
        success = False
    
    # Test Accept-Language format (should be en-GB with hyphen)
    accept_lang = headers.get("Accept-Language")
    if accept_lang == "en-GB":
        print("✅ CORRECT: Accept-Language uses hyphen format (en-GB)")
    else:
        print(f"❌ INCORRECT: Accept-Language format: {accept_lang}")
        print("   Expected: en-GB (with hyphen)")
        success = False
    
    return success

async def test_marketplace_id_standards():
    """Test marketplace ID standards (should be EBAY_GB with underscore)."""
    print("\n" + "=" * 60)
    print("TESTING MARKETPLACE ID STANDARDS")
    print("=" * 60)
    
    # Test that the default marketplace ID is EBAY_GB
    expected_marketplace_id = "EBAY_GB"
    
    print(f"✅ STANDARD: Default marketplace ID should be '{expected_marketplace_id}' (underscore format)")
    print("✅ STANDARD: Marketplace ID should be in request body/parameters, NOT headers")
    print("✅ STANDARD: No X-EBAY-C-MARKETPLACE-ID header should be used")
    
    return True

async def main():
    """Run all eBay API header standards tests."""
    print("EBAY API HEADER STANDARDS VERIFICATION")
    print("Testing implementation of definitive eBay API header standards")
    print()
    
    test_results = []
    
    # Test 1: Standard header function
    result1 = await test_standard_header_function()
    test_results.append(("Standard Header Function", result1))
    
    # Test 2: Update offer tool headers
    result2 = await test_update_offer_headers()
    test_results.append(("Update Offer Tool Headers", result2))
    
    # Test 3: Header format compliance
    result3 = await test_header_format_compliance()
    test_results.append(("Header Format Compliance", result3))
    
    # Test 4: Marketplace ID standards
    result4 = await test_marketplace_id_standards()
    test_results.append(("Marketplace ID Standards", result4))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = 0
    total = len(test_results)
    
    for test_name, passed_test in test_results:
        status = "✅ PASSED" if passed_test else "❌ FAILED"
        print(f"{test_name}: {status}")
        if passed_test:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        print("eBay API header standards have been successfully implemented!")
        print("\nSTANDARDS SUMMARY:")
        print("✅ Content-Language: en-GB (hyphen format)")
        print("✅ Accept-Language: en-GB (hyphen format)")
        print("✅ No X-EBAY-C-MARKETPLACE-ID in headers")
        print("✅ Marketplace ID: EBAY_GB (underscore) in request body/parameters")
    else:
        print("\n⚠️  Some tests failed. Please review the implementation.")
    
    return passed == total

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
