import os
import httpx


async def get_ebay_access_token() -> str:
    """Get eBay API access token using client ID and app IP"""
    client_id = os.getenv("EBAY_CLIENT_ID")
    app_id = os.getenv("EBAY_APP_ID")

    if not client_id or not app_id:
        return "EBAY_CLIENT_ID or EBAY_APP_ID is not set in environment variables"

    token_url = "https://api.ebay.com/identity/v1/oauth2/token"
    auth = httpx.BasicAuth(app_id, client_id)
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "grant_type": "client_credentials",
        "scope": "https://api.ebay.com/oauth/api_scope",
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
