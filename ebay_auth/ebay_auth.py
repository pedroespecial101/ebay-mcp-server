import os
import requests
import argparse
import logging
from base64 import b64encode
from dotenv import load_dotenv, set_key, find_dotenv
import webbrowser
import threading
import http.server
import socketserver
import queue
from urllib.parse import urlparse, parse_qs, urlencode
import uuid # For state parameter

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Constants --- 
TOKEN_ENDPOINT = "https://api.ebay.com/identity/v1/oauth2/token"
USER_API_ENDPOINT = "https://apiz.ebay.com/commerce/identity/v1/user/"
EBAY_AUTHORIZATION_ENDPOINT = "https://auth.ebay.com/oauth2/authorize"

DEFAULT_SCOPES = (
    "https://api.ebay.com/oauth/api_scope/commerce.identity.readonly",
)

LOCAL_SERVER_PORT = 9292 
LOCAL_CALLBACK_PATH = "/oauth/callback" # Must match eBay RuName redirection and local server path Cloudflare forwards to

DOTENV_PATH = find_dotenv()

if not DOTENV_PATH:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root_env = os.path.join(os.path.dirname(script_dir), '.env')
    if os.path.exists(project_root_env):
        DOTENV_PATH = project_root_env
    else:
        DOTENV_PATH = os.path.join(script_dir, '.env')
        logging.warning(f".env file not found. Attempting to use/create at: {DOTENV_PATH}")
        if not os.path.exists(DOTENV_PATH):
            with open(DOTENV_PATH, 'a') as f:
                pass # Create empty file
            logging.info(f"Created empty .env file at {DOTENV_PATH}")

load_dotenv(DOTENV_PATH)

# Global queue to pass authorization code/error from HTTP server thread to main thread
auth_response_queue = queue.Queue()
# Global variable to hold the server instance for shutdown
http_server_instance = None

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
            if value is not None:
                set_key(DOTENV_PATH, key, str(value)) # Ensure value is string
                logging.info(f"Saved {key} to .env: {str(value)[:10]}...")
            else:
                logging.warning(f"Skipped saving {key} to .env as its value is None.")
        load_dotenv(DOTENV_PATH, override=True) # Reload .env to reflect changes
        return True
    except Exception as e:
        logging.error(f"Error saving to .env file at {DOTENV_PATH}: {e}")
        return False

# --- Local HTTP Server for OAuth Callback ---
class OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_response_queue, http_server_instance
        parsed_path = urlparse(self.path)
        query_params = parse_qs(parsed_path.query)

        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()

        response_data = {}
        html_content = ""

        if 'code' in query_params:
            auth_code = query_params['code'][0]
            state_received = query_params.get('state', [None])[0]
            logging.info(f"Authorization code received by local server: {auth_code[:10]}...")
            # TODO: Validate state_received against a stored state if implementing CSRF protection fully
            response_data = {'auth_code': auth_code, 'error': None, 'state': state_received}
            html_content = f"""<html><head><title>eBay Auth In Progress</title></head><body>
                                <h1>Authentication In Progress...</h1>
                                <p>Authorization code received. Processing...</p>
                                <p>You can close this browser tab.</p>
                                </body></html>"""
        elif 'error' in query_params:
            error_details = {k: v[0] for k, v in query_params.items()}
            logging.error(f"Error received by local server during OAuth: {error_details}")
            response_data = {'error': error_details, 'auth_code': None}
            html_content = f"""<html><head><title>eBay Auth Error</title></head><body>
                                <h1>Authentication Failed</h1>
                                <p><b>Error:</b> {error_details.get('error', 'Unknown error')}</p>
                                <p><b>Details:</b> {error_details.get('error_description', 'No details')}</p>
                                <p>Please check the console output and try again.</p>
                                </body></html>"""
        else:
            unknown_error = 'No authorization code or error in query parameters.'
            logging.error(f"Unknown response received by local server: {self.path}")
            response_data = {'error': {'unknown': unknown_error}, 'auth_code': None}
            html_content = f"""<html><head><title>eBay Auth Error</title></head><body>
                                <h1>Unknown Response</h1><p>{unknown_error}</p>
                                <p>Please check the console output.</p>
                                </body></html>"""
        
        self.wfile.write(html_content.encode('utf-8'))
        auth_response_queue.put(response_data)

        if http_server_instance:
            logging.info("Shutting down local HTTP server...")
            threading.Thread(target=http_server_instance.shutdown).start()

    def log_message(self, format, *args):
        # Suppress most logs, only show errors or specific info
        if "error" in format.lower() or (args and any("error" in str(arg).lower() for arg in args)):
            super().log_message(format, *args)
        elif "info" in format.lower() and ("server" in format.lower() or "shutting down" in format.lower()):
            super().log_message(format, *args)

def _start_local_http_server(port, path_segment):
    global http_server_instance
    # The RuName should be configured to redirect to http://localhost:{port}{path_segment}
    # Example: http://localhost:8000/ebay_auth_callback
    # The handler will receive the full path including the path_segment.
    try:
        http_server_instance = socketserver.TCPServer(("localhost", port), OAuthCallbackHandler)
        logging.info(f"Local HTTP server started on http://localhost:{port}")
        logging.info(f"Waiting for eBay to redirect to your configured RuName (which should forward to http://localhost:{port}{path_segment})...")
        http_server_instance.serve_forever()
        logging.info("Local HTTP server stopped.")
    except Exception as e:
        logging.error(f"Error starting or running local HTTP server: {e}")
        auth_response_queue.put({'error': {'server_error': str(e)}, 'auth_code': None})
    finally:
        if http_server_instance:
            http_server_instance.server_close()

# --- Core Authentication Functions --- 

def _exchange_auth_code_and_get_user_details(auth_code):
    """Exchanges authorization code for tokens and fetches user details."""
    logging.info(f"Exchanging authorization code for token: {auth_code[:10]}...")

    client_id = get_env_variable("EBAY_CLIENT_ID")
    client_secret = get_env_variable("EBAY_CLIENT_SECRET")
    # EBAY_RU_NAME is the *name* of the redirect URI configuration on eBay's side.
    # The actual redirect_uri parameter sent in the token exchange request must be the *value* 
    # that eBay will redirect to. This is the public URL like 'https://yourdomain.com/oauth/callback'.
    redirect_uri_value = get_env_variable("EBAY_APP_CONFIGURED_REDIRECT_URI")

    if not all([client_id, client_secret, auth_code, redirect_uri_value]):
        logging.error("Missing CLIENT_ID, CLIENT_SECRET, auth_code, or EBAY_APP_CONFIGURED_REDIRECT_URI for token exchange.")
        return None, None, None, None # access_token, refresh_token, user_id, user_name

    payload = {
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": redirect_uri_value
    }
    auth_header_val = f"{client_id}:{client_secret}"
    auth_header = b64encode(auth_header_val.encode()).decode()
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {auth_header}"
    }

    try:
        response = requests.post(TOKEN_ENDPOINT, data=payload, headers=headers)
        response.raise_for_status()
        token_data = response.json()
        
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token") # eBay usually provides this
        # expires_in = token_data.get("expires_in") # Can be used to proactively refresh

        if not access_token:
            logging.error("Access token not found in eBay response during code exchange.")
            logging.debug(f"Full token exchange response: {token_data}")
            return None, None, None, None

        logging.info(f"Access token received: {access_token[:10]}...")
        if refresh_token:
            logging.info(f"Refresh token received: {refresh_token[:10]}...")
        else:
            logging.warning("Refresh token NOT received during initial code exchange. This is unusual.")

        # Save new tokens to .env
        env_vars_to_save = {"EBAY_USER_ACCESS_TOKEN": access_token}
        if refresh_token:
            env_vars_to_save["EBAY_USER_REFRESH_TOKEN"] = refresh_token
        _save_to_env(env_vars_to_save)

        # Now get user details using the new access token
        user_id, user_name = get_user_details(access_token=access_token)
        if user_id and user_name:
            logging.info(f"Successfully fetched user details after token exchange: UserID={user_id}, UserName={user_name}")
        else:
            logging.warning("Could not fetch user details after obtaining new tokens. Tokens saved, but user info might be missing in .env.")
        
        return access_token, refresh_token, user_id, user_name

    except requests.exceptions.HTTPError as e:
        logging.error(f"HTTP error during token exchange: {e}")
        if e.response is not None:
            logging.error(f"Response content: {e.response.text}")
        return None, None, None, None
    except requests.exceptions.RequestException as e:
        logging.error(f"Request failed during token exchange: {e}")
        return None, None, None, None
    except Exception as e:
        logging.error(f"An unexpected error occurred during token exchange: {e}")
        return None, None, None, None

def initiate_user_login():
    """Initiates the full eBay OAuth2 user login flow."""
    logging.info("Initiating eBay user login process...")

    client_id = get_env_variable("EBAY_CLIENT_ID")
    # EBAY_RU_NAME is the *identifier* for your redirect URI configuration on eBay's side.
    # This is what you pass as the 'redirect_uri' parameter in the authorization request.
    ebay_ru_name = get_env_variable("EBAY_RU_NAME") 

    if not client_id or not ebay_ru_name:
        logging.error("EBAY_CLIENT_ID or EBAY_RU_NAME not found in .env. Cannot initiate login.")
        return False

    # The actual URL where eBay will send the user back. This must match what's configured for EBAY_RU_NAME.
    # For this script, it's our local server.
    # This value is used by the local server to know it's the correct callback,
    # and also in the token exchange step as the `redirect_uri` parameter.
    configured_redirect_uri_value = f"http://localhost:{LOCAL_SERVER_PORT}{LOCAL_CALLBACK_PATH}"

    # Generate a unique state parameter for CSRF protection
    oauth_state = str(uuid.uuid4())
    # TODO: Store this oauth_state temporarily (e.g., in a short-lived file or global var) 
    # to validate it when the callback is received.

    auth_url_params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": ebay_ru_name, # Use the RuName here as per eBay docs for auth request
        "scope": ' '.join(s.strip() for s in DEFAULT_SCOPES),
        "prompt": "login", # Optional: forces user to login even if already sessioned with eBay
        "state": oauth_state # For CSRF protection
    }
    authorization_url = f"{EBAY_AUTHORIZATION_ENDPOINT}?{urlencode(auth_url_params)}"

    logging.info(f"Opening browser to: {EBAY_AUTHORIZATION_ENDPOINT} with query params...")
    webbrowser.open(authorization_url)

    # Start local HTTP server in a new thread
    # It will listen at configured_redirect_uri_value (e.g., http://localhost:8000/ebay_auth_callback)
    server_thread = threading.Thread(target=_start_local_http_server, args=(LOCAL_SERVER_PORT, LOCAL_CALLBACK_PATH))
    server_thread.daemon = True # Allow main program to exit even if server thread is running
    server_thread.start()

    logging.info("Waiting for authorization response from local server...")
    try:
        # Wait for response from OAuthCallbackHandler (via queue)
        # Timeout can be added here if needed: auth_response_queue.get(timeout=300)
        auth_response = auth_response_queue.get(block=True) 
    except queue.Empty:
        logging.error("Timeout waiting for authorization response from local server.")
        return False
    
    server_thread.join(timeout=5) # Wait a bit for server thread to finish cleanly

    if auth_response.get('error'):
        logging.error(f"Error during initial OAuth authorization: {auth_response['error']}")
        return False

    auth_code = auth_response.get('auth_code')
    received_state = auth_response.get('state')

    # TODO: Validate received_state against the oauth_state generated earlier
    # if received_state != oauth_state:
    #     logging.error("OAuth state mismatch. Possible CSRF attack.")
    #     return False
    # logging.info("OAuth state validated successfully.")

    if not auth_code:
        logging.error("No authorization code received from callback.")
        return False

    access_token, refresh_token, user_id, user_name = _exchange_auth_code_and_get_user_details(auth_code)

    if access_token and user_id:
        logging.info("Successfully obtained tokens and user details.")
        print(f"\n--- eBay Login Successful ---")
        print(f"User Name: {user_name}")
        print(f"User ID: {user_id}")
        print(f"Access Token: {access_token[:15]}... (saved to .env)")
        if refresh_token:
            print(f"Refresh Token: {refresh_token[:15]}... (saved to .env)")
        print("-----------------------------")
        return True
    else:
        logging.error("Failed to obtain tokens or user details after authorization.")
        return False

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
        "scope": ' '.join(s.strip() for s in DEFAULT_SCOPES), # Recommended to include scopes
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
        
        new_refresh_token = token_data.get("refresh_token")
        
        env_vars_to_save = {"EBAY_USER_ACCESS_TOKEN": new_access_token}
        if new_refresh_token and new_refresh_token != current_refresh_token:
            logging.info(f"New refresh token received and saved: {new_refresh_token[:10]}...")
            env_vars_to_save["EBAY_USER_REFRESH_TOKEN"] = new_refresh_token
        elif new_refresh_token:
            logging.info("Refresh token re-issued but is the same as current. Not re-saving unless different.")
        else:
            logging.info("Refresh token was not re-issued during this refresh cycle.")

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
    
    access_token_to_use = access_token or get_env_variable("EBAY_USER_ACCESS_TOKEN")

    if not access_token_to_use:
        logging.warning("No access token for get_user_details. Trying to refresh.")
        access_token_to_use = refresh_access_token()
        if not access_token_to_use:
            logging.error("Failed to obtain access token for fetching user details.")
            return None, None
    
    logging.info(f"Using access token for user details: {access_token_to_use[:10]}...")
    headers = {
        "Authorization": f"Bearer {access_token_to_use}",
        "Accept": "application/json"
    }

    try:
        response = requests.get(USER_API_ENDPOINT, headers=headers)
        response.raise_for_status()
        user_data = response.json()
        
        user_id = user_data.get("userId")
        user_name = user_data.get("username")

        if not user_id or not user_name:
            logging.error("Could not find 'userId' or 'username' in API response for get_user_details.")
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
            if e.response.status_code == 401:
                logging.info("Access token might be expired during get_user_details. Attempting refresh...")
                # Avoid recursive loop if refresh_access_token itself called get_user_details
                # Only refresh if we weren't given an access_token to begin with.
                if access_token is None: # This means we used one from .env or got it from a fresh refresh_access_token call
                    new_access_token = refresh_access_token()
                    if new_access_token:
                        logging.info("Token refreshed. Retrying get_user_details with newly refreshed token...")
                        return get_user_details(access_token=new_access_token) 
                    else:
                        logging.error("Failed to refresh token after 401 in get_user_details.")
                else:
                    logging.warning("An access_token was provided to get_user_details and it failed with 401. Not attempting auto-refresh here.")
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
        choices=["get_user", "refresh_token", "login"], 
        help="Action to perform: 'login' to initiate full OAuth flow, 'get_user' to fetch eBay UserID/UserName, 'refresh_token' to refresh access token."
    )

    args = parser.parse_args()

    if args.action == "login":
        initiate_user_login()
    elif args.action == "get_user":
        user_id, user_name = get_user_details()
        if user_id and user_name:
            print(f"\n--- eBay User Details ---")
            print(f"User Name: {user_name}")
            print(f"User ID: {user_id}")
            print(f"(Fetched from .env or API)")
            print("-------------------------")
        else:
            print("Could not retrieve eBay user details. Check logs.")
    elif args.action == "refresh_token":
        new_token = refresh_access_token()
        if new_token:
            print(f"\n--- Token Refresh Successful ---")
            print(f"New Access Token: {new_token[:15]}... (saved to .env)")
            print("------------------------------")
        else:
            print("Failed to refresh access token. Check logs.")
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
