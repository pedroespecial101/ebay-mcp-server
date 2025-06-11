#!/usr/bin/env python3
"""
Comprehensive test script for the updated Update Offer MCP tool.
Tests all new fields and validates the REPLACE operation behavior.
"""

import asyncio
import json
import sys
import os

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from src.models.mcp_tools import UpdateOfferParams
from src.models.ebay.inventory import UpdateOfferRequest

def test_update_offer_params_validation():
    """Test the comprehensive UpdateOfferParams model validation."""
    print("Testing UpdateOfferParams validation...")
    
    # Test basic required field
    try:
        params = UpdateOfferParams(offer_id="12345")
        print("✓ Basic offer_id validation passed")
    except Exception as e:
        print(f"✗ Basic validation failed: {e}")
        return False
    
    # Test SKU length validation
    try:
        params = UpdateOfferParams(offer_id="12345", sku="a" * 51)  # Too long
        print("✗ SKU length validation should have failed")
        return False
    except ValueError as e:
        print("✓ SKU length validation passed")
    
    # Test quantity validations
    try:
        params = UpdateOfferParams(offer_id="12345", available_quantity=-1)
        print("✗ Negative quantity validation should have failed")
        return False
    except ValueError as e:
        print("✓ Negative quantity validation passed")
    
    try:
        params = UpdateOfferParams(offer_id="12345", quantity_limit_per_buyer=0)
        print("✗ Zero quantity limit validation should have failed")
        return False
    except ValueError as e:
        print("✓ Quantity limit validation passed")
    
    # Test comprehensive field assignment
    try:
        params = UpdateOfferParams(
            offer_id="12345",
            sku="TEST-SKU-001",
            marketplace_id="EBAY_US",
            available_quantity=10,
            pricing_summary={"price": {"currency": "USD", "value": "29.99"}},
            category_id="12345",
            listing_description="Test product description",
            listing_duration="GTC",
            merchant_location_key="warehouse-001",
            listing_policies={
                "paymentPolicyId": "payment-123",
                "returnPolicyId": "return-123",
                "fulfillmentPolicyId": "fulfillment-123"
            },
            store_category_names=["/Electronics/Computers"],
            quantity_limit_per_buyer=5,
            hide_buyer_details=True,
            include_catalog_product_details=False,
            tax={"applyTax": True}
        )
        print("✓ Comprehensive field validation passed")
    except Exception as e:
        print(f"✗ Comprehensive validation failed: {e}")
        return False
    
    return True

def test_update_offer_request_model():
    """Test the UpdateOfferRequest model."""
    print("\nTesting UpdateOfferRequest model...")
    
    try:
        request = UpdateOfferRequest(
            offer_id="12345",
            sku="TEST-SKU-001",
            marketplace_id="EBAY_US",
            available_quantity=10,
            pricing_summary={"price": {"currency": "USD", "value": "29.99"}},
            category_id="12345",
            listing_description="Test product description",
            listing_duration="GTC",
            merchant_location_key="warehouse-001"
        )
        
        # Test model_dump (Pydantic v2)
        data = request.model_dump(exclude_none=True)
        print("✓ UpdateOfferRequest model creation and serialization passed")
        print(f"  Serialized fields: {list(data.keys())}")
        
    except Exception as e:
        print(f"✗ UpdateOfferRequest model failed: {e}")
        return False
    
    return True

def test_field_coverage():
    """Test that all eBay API fields are covered."""
    print("\nTesting field coverage against eBay API specification...")
    
    # Fields from EbayOfferDetailsWithId schema
    expected_fields = {
        'offer_id', 'sku', 'marketplace_id', 'available_quantity', 'category_id',
        'charity', 'extended_producer_responsibility', 'hide_buyer_details',
        'include_catalog_product_details', 'listing_description', 'listing_duration',
        'listing_policies', 'listing_start_date', 'lot_size', 'merchant_location_key',
        'pricing_summary', 'quantity_limit_per_buyer', 'regulatory',
        'secondary_category_id', 'store_category_names', 'tax'
    }
    
    # Get fields from UpdateOfferParams
    params_fields = set(UpdateOfferParams.model_fields.keys())
    
    # Get fields from UpdateOfferRequest  
    request_fields = set(UpdateOfferRequest.model_fields.keys())
    
    print(f"UpdateOfferParams fields: {len(params_fields)}")
    print(f"UpdateOfferRequest fields: {len(request_fields)}")
    print(f"Expected eBay API fields: {len(expected_fields)}")
    
    # Check coverage
    missing_in_params = expected_fields - params_fields
    missing_in_request = expected_fields - request_fields
    
    if missing_in_params:
        print(f"✗ Missing fields in UpdateOfferParams: {missing_in_params}")
        return False
    
    if missing_in_request:
        print(f"✗ Missing fields in UpdateOfferRequest: {missing_in_request}")
        return False
    
    print("✓ All expected eBay API fields are covered")
    return True

def test_documentation_warnings():
    """Test that critical warnings are present in documentation."""
    print("\nTesting documentation warnings...")
    
    params_doc = UpdateOfferParams.__doc__
    request_doc = UpdateOfferRequest.__doc__
    
    critical_terms = ["REPLACE", "COMPLETE REPLACEMENT", "overwritten", "cleared"]
    
    for doc, model_name in [(params_doc, "UpdateOfferParams"), (request_doc, "UpdateOfferRequest")]:
        if not doc:
            print(f"✗ {model_name} missing documentation")
            return False
        
        found_warnings = [term for term in critical_terms if term.lower() in doc.lower()]
        if not found_warnings:
            print(f"✗ {model_name} missing critical warnings about REPLACE operation")
            return False
        
        print(f"✓ {model_name} contains critical warnings: {found_warnings}")
    
    return True

def main():
    """Run all tests."""
    print("=" * 60)
    print("COMPREHENSIVE UPDATE OFFER MCP TOOL TESTS")
    print("=" * 60)
    
    tests = [
        test_update_offer_params_validation,
        test_update_offer_request_model,
        test_field_coverage,
        test_documentation_warnings
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                print(f"✗ {test.__name__} FAILED")
        except Exception as e:
            print(f"✗ {test.__name__} FAILED with exception: {e}")
    
    print("\n" + "=" * 60)
    print(f"TEST RESULTS: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED! The Update Offer tool is ready for comprehensive use.")
        print("\n⚠️  REMEMBER: This is a REPLACE operation!")
        print("   Always retrieve current offer data first to preserve existing values.")
    else:
        print("❌ Some tests failed. Please review and fix issues before using.")
    
    print("=" * 60)
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
