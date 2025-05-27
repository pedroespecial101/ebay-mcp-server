import os
from dotenv import load_dotenv
import httpx

# Get the absolute path to the directory where this script is located
script_dir = os.path.dirname(os.path.abspath(__file__))

# Construct the path to the project root (assuming .env is in the parent directory of src)
project_root = os.path.join(script_dir, '..')

# Load environment variables from .env file in the project root
print(f"Attempting to load .env from: {os.path.join(project_root, '.env')}")
load_dotenv(os.path.join(project_root, '.env'))


async def get_ebay_access_token() -> str:
    """Get eBay API access token using either the provided OAuth token or client credentials."""
    # First, check if we have a direct OAuth token in the environment
    oauth_token = os.getenv("EBAY_OAUTH_TOKEN")
    if oauth_token:
        print("Using provided OAuth token")
        return oauth_token
        
    print("No OAuth token found, falling back to client credentials flow")
    client_id = os.getenv("EBAY_CLIENT_ID")
    app_id = os.getenv("EBAY_APP_ID")

    if not client_id or not app_id:
        return "EBAY_CLIENT_ID or EBAY_APP_ID is not set in environment variables"

    token_url = "https://api.ebay.com/identity/v1/oauth2/token"
    auth = httpx.BasicAuth(app_id, client_id)
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
    }
    # Define all required scopes with their descriptions
    scopes = [
        # Public data access
        "https://api.ebay.com/oauth/api_scope",  # View public data from eBay
        
        # Marketing scopes
        "https://api.ebay.com/oauth/api_scope/sell.marketing.readonly",  # View your eBay marketing activities
        "https://api.ebay.com/oauth/api_scope/sell.marketing",  # View and manage your eBay marketing activities
        
        # Inventory scopes
        "https://api.ebay.com/oauth/api_scope/sell.inventory.readonly",  # View your inventory and offers
        "https://api.ebay.com/oauth/api_scope/sell.inventory",  # View and manage your inventory and offers
        
        # Account scopes
        "https://api.ebay.com/oauth/api_scope/sell.account.readonly",  # View your account settings
        "https://api.ebay.com/oauth/api_scope/sell.account",  # View and manage your account settings
        
        # Fulfillment scopes
        "https://api.ebay.com/oauth/api_scope/sell.fulfillment.readonly",  # View your order fulfillments
        "https://api.ebay.com/oauth/api_scope/sell.fulfillment",  # View and manage your order fulfillments
        
        # Analytics and finances
        "https://api.ebay.com/oauth/api_scope/sell.analytics.readonly",  # View your selling analytics data
        "https://api.ebay.com/oauth/api_scope/sell.finances",  # View and manage payment and order information
        
        # Payment disputes
        "https://api.ebay.com/oauth/api_scope/sell.payment.dispute",  # View and manage disputes
        
        # Identity and reputation
        "https://api.ebay.com/oauth/api_scope/commerce.identity.readonly",  # View user's basic information
        "https://api.ebay.com/oauth/api_scope/sell.reputation.readonly",  # View your reputation data
        "https://api.ebay.com/oauth/api_scope/sell.reputation",  # View and manage your reputation data
        
        # Notifications
        "https://api.ebay.com/oauth/api_scope/commerce.notification.subscription.readonly",  # View your event notifications
        "https://api.ebay.com/oauth/api_scope/commerce.notification.subscription",  # View and manage your event notifications
        
        # Stores
        "https://api.ebay.com/oauth/api_scope/sell.stores.readonly",  # View eBay stores
        "https://api.ebay.com/oauth/api_scope/sell.stores",  # View and manage eBay stores
        
        # eDelivery
        "https://api.ebay.com/oauth/scope/sell.edelivery"  # Access to eDelivery International Shipping APIs
    ]
    
    data = {
        "grant_type": "client_credentials",
        "scope": " ".join(scopes),  # Join all scopes with spaces
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                token_url, headers=headers, data=data, auth=auth
            )
            if response.status_code != 200:
                return f"Failed to get access token: {response.status_code} {response.text}"
            return response.json().get("access_token", "No access token found")
        except Exception as e:
            return f"Error occurred when requesting access token: {e}"
