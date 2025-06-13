"""
Centralized configuration management for the eBay MCP server.

This module uses pydantic-settings to load configuration from environment variables
and .env files, allowing for a flexible and secure way to manage settings.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class EbayOfferDefaults(BaseSettings):
    """
    Loads default eBay offer settings from environment variables.

    These settings are used internally by the manage_offer tool and are not
    exposed as parameters to the LLM. This keeps the tool interface clean
    while allowing for easy configuration of default offer values.
    """

    # Configure pydantic-settings to load from a .env file
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # eBay API Default Settings
    EBAY_MARKETPLACE_ID: str = "EBAY_GB"
    EBAY_PAYMENT_POLICY_ID: str
    EBAY_RETURN_POLICY_ID: str
    EBAY_FULFILLMENT_POLICY_ID: str
    EBAY_MERCHANT_LOCATION_KEY: str
    EBAY_LISTING_FORMAT: str = "FIXED_PRICE"
    EBAY_LISTING_DURATION: str = "GTC"
    EBAY_LISTING_INCLUDE_CATALOG_PRODUCT_DETAILS: bool = True


# Create a single, reusable instance of the settings
ebay_offer_defaults = EbayOfferDefaults()
