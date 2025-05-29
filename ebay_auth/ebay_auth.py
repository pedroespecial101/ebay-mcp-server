import os
import requests
import argparse
import logging
from base64 import b64encode
from dotenv import load_dotenv, set_key, find_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Constants --- 
# (These should ideally be configurable or passed if this module is truly standalone)
TOKEN_ENDPOINT = "https://api.ebay.com/identity/v1/oauth2/token"
USER_API_ENDPOINT = "https://apiz.ebay.com/commerce/identity/v1/user/"
DOTENV_PATH = find_dotenv() # Finds .env in the current dir or parent dirs

if not DOTENV_PATH:
    # If .env is not found by find_dotenv, try to create it in the script's directory or project root
    # This is a fallback, ideally .env should exist where your main project runs
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root_env = os.path.join(os.path.dirname(script_dir), '.env') # Assuming ebay_auth is one level down
    
    if os.path.exists(project_root_env):
        DOTENV_PATH = project_root_env
    else:
        # As a last resort, try to create .env in the script's own directory
        # This might not be ideal if the module is used from elsewhere
        DOTENV_PATH = os.path.join(script_dir, '.env')
        logging.warning(f".env file not found. Attempting to use/create at: {DOTENV_PATH}")
        # Create if it doesn't exist, so set_key can work
        if not os.path.exists(DOTENV_PATH):
            open(DOTENV_PATH, 'a').close()
            logging.info(f"Created empty .env file at {DOTENV_PATH}")

load_dotenv(DOTENV_PATH) # Load existing .env file if found

# --- Helper Functions --- 

def get_env_variable(var_name, default=None):
    """Fetches an environment variable. Logs if not found and no default is provided."""
    value = os.getenv(var_name)
    if value is None and default is None:
        logging.warning(f"Environment variable {var_name} not found and no default value provided.")
    elif value is None:
        logging.info(f"Environment variable {var_name} not found. Using default value.")
        return default
    return value

def _save_to_env(key_values):
    """Saves or updates multiple key-value pairs in the .env file."""
    if not DOTENV_PATH:
        logging.error("Cannot save to .env file: Path not determined.")
        return False
    try:
        for key, value in key_values.items():
            if value is not None: # Only save if value is not None
                set_key(DOTENV_PATH, key, value)
                logging.info(f"Saved {key} to .env: {str(value)[:10]}...")
            else:
                logging.warning(f"Skipped saving {key} to .env as its value is None.")
        load_dotenv(DOTENV_PATH, override=True) # Reload .env to reflect changes
        return True
    except Exception as e:
        logging.error(f"Error saving to .env file at {DOTENV_PATH}: {e}")
        return False

# --- Core Authentication Functions --- 

def refresh_access_token(client_id=None, client_secret=None, refresh_token_val=None):
    """Refreshes the eBay access token using the refresh token."""
    logging.info("Attempting to refresh eBay access token...")

    client_id = client_id or get_env_variable("EBAY_CLIENT_ID")
    client_secret = client_secret or get_env_variable("EBAY_CLIENT_SECRET")
    current_refresh_token = refresh_token_val or get_env_variable("EBAY_USER_REFRESH_TOKEN")

    if not all([client_id, client_secret, current_refresh_token]):
        logging.error("Missing CLIENT_ID, CLIENT_SECRET, or REFRESH_TOKEN for token refresh.")
        return None

    payload = {
        "grant_type": "refresh_token",
        "refresh_token": current_refresh_token,
        # "scope": "your_required_scopes" # Optional: if you need to adjust scopes
    }
    auth_header_val = f"{client_id}:{client_secret}"
    auth_header = b64encode(auth_header_val.encode()).decode()
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {auth_header}"
    }

    try:
        logging.info(f"Requesting new access token from {TOKEN_ENDPOINT} using refresh token: {current_refresh_token[:10]}...")
        response = requests.post(TOKEN_ENDPOINT, data=payload, headers=headers)
        response.raise_for_status()
        token_data = response.json()
        new_access_token = token_data.get("access_token")

        if not new_access_token:
            logging.error("Failed to get new access token. No 'access_token' in response.")
            logging.debug(f"Full response from token endpoint: {token_data}")
            return None

        logging.info(f"Successfully refreshed access token: {new_access_token[:10]}...")
        
        # eBay refresh token might be long-lived and often isn't re-issued on access token refresh.
        # However, if it IS re-issued, the new one should be saved.
        new_refresh_token = token_data.get("refresh_token") # Check if a new one is provided
        
        env_vars_to_save = {"EBAY_USER_ACCESS_TOKEN": new_access_token}
        if new_refresh_token and new_refresh_token != current_refresh_token:
            logging.info(f"New refresh token received: {new_refresh_token[:10]}...")
            env_vars_to_save["EBAY_USER_REFRESH_TOKEN"] = new_refresh_token
        else:
            logging.info("Refresh token was not re-issued or is unchanged.")

        _save_to_env(env_vars_to_save)
        return new_access_token

    except requests.exceptions.HTTPError as e:
        logging.error(f"HTTP error refreshing token: {e}")
        if e.response is not None:
            logging.error(f"Response content: {e.response.text}")
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Request failed refreshing token: {e}")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred during token refresh: {e}")
        return None

def get_user_details(access_token=None):
    """Fetches eBay user ID and username using the access token."""
    logging.info("Attempting to fetch eBay user details...")
    
    access_token = access_token or get_env_variable("EBAY_USER_ACCESS_TOKEN")

    if not access_token:
        logging.warning("No access token provided or found in .env. Trying to refresh.")
        access_token = refresh_access_token()
        if not access_token:
            logging.error("Failed to obtain access token for fetching user details.")
            return None, None
    
    logging.info(f"Using access token for user details: {access_token[:10]}...")
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }

    try:
        response = requests.get(USER_API_ENDPOINT, headers=headers)
        response.raise_for_status()
        user_data = response.json()
        
        user_id = user_data.get("userId")
        user_name = user_data.get("username")

        if not user_id or not user_name:
            logging.error("Could not find 'userId' or 'username' in API response.")
            logging.debug(f"Full user API response: {user_data}")
            return None, None

        logging.info(f"Fetched user details: UserID={user_id}, UserName={user_name}")
        _save_to_env({
            "EBAY_USER_ID": user_id,
            "EBAY_USER_NAME": user_name
        })
        return user_id, user_name

    except requests.exceptions.HTTPError as e:
        logging.error(f"HTTP error fetching user details: {e}")
        if e.response is not None:
            logging.error(f"Response content: {e.response.text}")
            # Check for 401 Unauthorized, which might mean token expired
            if e.response.status_code == 401:
                logging.info("Access token might be expired. Attempting refresh...")
                new_access_token = refresh_access_token()
                if new_access_token:
                    logging.info("Token refreshed. Retrying get_user_details...")
                    return get_user_details(access_token=new_access_token) # Recursive call with new token
                else:
                    logging.error("Failed to refresh token after 401 error.")
        return None, None
    except requests.exceptions.RequestException as e:
        logging.error(f"Request failed fetching user details: {e}")
        return None, None
    except Exception as e:
        logging.error(f"An unexpected error occurred fetching user details: {e}")
        return None, None

# --- Command-Line Interface --- 

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="eBay Authentication Helper.")
    parser.add_argument(
        "action", 
        choices=["get_user", "refresh_token"], 
        help="Action to perform: 'get_user' to fetch and display eBay UserID/UserName, 'refresh_token' to refresh the access token."
    )
    parser.add_argument(
        "--env_path",
        type=str,
        default=None,
        help="Path to the .env file. If not provided, will search for .env in standard locations."
    )

    args = parser.parse_args()

    if args.env_path:
        if os.path.exists(args.env_path):
            DOTENV_PATH = args.env_path
            load_dotenv(DOTENV_PATH, override=True)
            logging.info(f"Using .env file specified at: {DOTENV_PATH}")
        else:
            logging.error(f".env file specified at {args.env_path} not found. Exiting.")
            exit(1)
    elif not DOTENV_PATH or not os.path.exists(DOTENV_PATH):
        logging.error("Could not find or determine a .env file path. Please specify with --env_path or ensure .env exists. Exiting.")
        exit(1)
    
    logging.info(f"Using .env file at: {DOTENV_PATH}")

    if args.action == "get_user":
        print("Fetching eBay User ID and User Name...")
        user_id, user_name = get_user_details()
        if user_id and user_name:
            print(f"\n--- eBay User Information ---")
            print(f"eBay User ID:   {user_id}")
            print(f"eBay User Name: {user_name}")
            print(f"(These details have also been updated in {DOTENV_PATH})\n")
        else:
            print("\nFailed to retrieve eBay user information. Check logs for details.\n")
    
    elif args.action == "refresh_token":
            print("Attempting to refresh eBay access token...")
            new_token = refresh_access_token()
            if new_token:
                print(f"\nAccess token refreshed successfully: {new_token[:10]}...")
                print(f"(Token has been updated in {DOTENV_PATH})\n")
            else:
                print("\nFailed to refresh access token. Check logs for details.\n")
