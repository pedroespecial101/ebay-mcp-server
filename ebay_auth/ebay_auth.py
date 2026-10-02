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
import shutil
import subprocess
from urllib.parse import urlparse, parse_qs, urlencode
import uuid # For state parameter

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Constants --- 
TOKEN_ENDPOINT = "https://api.ebay.com/identity/v1/oauth2/token"
USER_API_ENDPOINT = "https://apiz.ebay.com/commerce/identity/v1/user/"
EBAY_AUTHORIZATION_ENDPOINT = "https://auth.ebay.com/oauth2/authorize"

DEFAULT_SCOPES = (
    "https://api.ebay.com/oauth/api_scope",
    "https://api.ebay.com/oauth/api_scope/sell.inventory",
    "https://api.ebay.com/oauth/api_scope/commerce.identity.readonly",
    "https://api.ebay.com/oauth/api_scope/sell.fulfillment.readonly",
)

LOCAL_SERVER_PORT = 9292 
LOCAL_CALLBACK_PATH = "/oauth/callback" # Must match eBay RuName redirection and local server path Cloudflare forwards to

def _resolve_dotenv_path():
    credentials_file = os.getenv("EBAY_CREDENTIALS_FILE")
    if credentials_file:
        return os.path.expanduser(credentials_file)

    if os.getenv("EBAY_TOKEN_STORE", "").lower() == "doppler":
        return None

    dotenv_path = find_dotenv()
    if dotenv_path:
        return dotenv_path

    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root_env = os.path.join(os.path.dirname(script_dir), '.env')
    if os.path.exists(project_root_env):
        return project_root_env

    return None


DOTENV_PATH = _resolve_dotenv_path()

if DOTENV_PATH:
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
    """Update process auth state and persist it to the configured token store."""
    values = {key: str(value) for key, value in key_values.items() if value is not None}
    os.environ.update(values)

    if os.getenv("EBAY_TOKEN_STORE", "").lower() == "doppler":
        return _save_to_doppler(values)

    if not DOTENV_PATH:
        logging.info("Updated eBay auth state for the current process only.")
        return True

    try:
        parent_dir = os.path.dirname(DOTENV_PATH)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        for key, value in values.items():
            success, key_written, _ = set_key(DOTENV_PATH, key, value)
            if success:
                logging.info("Saved %s to the configured credentials file.", key_written)
            else:
                logging.error("Failed to save %s to the configured credentials file.", key)
        load_dotenv(DOTENV_PATH, override=True) # Reload .env to reflect changes
        return True
    except Exception as e:
        logging.error(f"Error saving to .env file at {DOTENV_PATH}: {e}")
        return False


def _save_to_doppler(key_values):
    """Persist durable seller auth state without storing short-lived access tokens."""
    durable_keys = {"EBAY_USER_REFRESH_TOKEN", "EBAY_USER_ID", "EBAY_USER_NAME"}
    values = {key: value for key, value in key_values.items() if key in durable_keys}
    if not values:
        return True

    project = os.getenv("DOPPLER_PROJECT")
    config = os.getenv("DOPPLER_CONFIG")
    if not project or not config or not shutil.which("doppler"):
        logging.error("Doppler token persistence requires DOPPLER_PROJECT, DOPPLER_CONFIG, and the Doppler CLI.")
        return False

    for key, value in values.items():
        command = [
            "doppler", "secrets", "set", key,
            "--project", project,
            "--config", config,
            "--silent",
        ]
        try:
            subprocess.run(
                command,
                input=value,
                text=True,
                capture_output=True,
                check=True,
            )
            logging.info("Saved %s to Doppler project %s/%s.", key, project, config)
        except subprocess.CalledProcessError:
            logging.exception("Failed to save %s to Doppler project %s/%s.", key, project, config)
            return False
    return True

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
            logging.info("Authorization code received by local server.")
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
        # Allow the port to be reused immediately
        socketserver.TCPServer.allow_reuse_address = True
        http_server_instance = socketserver.TCPServer(("", port), OAuthCallbackHandler)
        logging.info(f"Local HTTP server started on port {port}, listening on all available interfaces (reuse_address enabled).")
        logging.info(f"Waiting for eBay to redirect to your configured RuName (which should forward to a local address on port {port} at path {path_segment})...")
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
    logging.info("Exchanging authorization code for tokens.")

    client_id = get_env_variable("EBAY_CLIENT_ID")
    client_secret = get_env_variable("EBAY_CLIENT_SECRET")
    # EBAY_RU_NAME is the *name* of the redirect URI configuration on eBay's side.
    # The actual redirect_uri parameter sent in the token exchange request must be the *value* 
    # that eBay will redirect to. This is the public URL like 'https://yourdomain.com/oauth/callback'.
    redirect_uri_value = get_env_variable("EBAY_APP_CONFIGURED_REDIRECT_URI")

    if not all([client_id, client_secret, auth_code, redirect_uri_value]):
        logging.error("Missing CLIENT_ID, CLIENT_SECRET, auth_code, or EBAY_APP_CONFIGURED_REDIRECT_URI for token exchange.")
        return {"status": "error", "message": "Configuration error for token exchange.", "error_details": "Missing credentials or redirect URI."}

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
            return {"status": "error", "message": "Access token not found in eBay response.", "error_details": token_data}

        logging.info("Access token received.")
        if refresh_token:
            logging.info("Refresh token received.")
        else:
            logging.warning("Refresh token NOT received during initial code exchange. This is unusual.")

        # Now get user details using the new access token
        user_id, user_name = get_user_details(access_token=access_token)

        if access_token and user_id and user_name:
            logging.info("Successfully fetched tokens and user details for user %s.", user_name)
            env_vars_to_save = {
                "EBAY_USER_ACCESS_TOKEN": access_token,
                "EBAY_USER_ID": user_id,
                "EBAY_USER_NAME": user_name
            }
            if refresh_token:
                env_vars_to_save["EBAY_USER_REFRESH_TOKEN"] = refresh_token
            
            if _save_to_env(env_vars_to_save):
                logging.info("Seller authentication state saved successfully.")
            else:
                logging.error("Failed to save all seller authentication state.")
                # Decide if we should return None here if saving fails critically
        elif access_token: # We got tokens but not user details
            logging.warning("Obtained tokens but failed to fetch user details. Saving tokens only.")
            env_vars_to_save = {"EBAY_USER_ACCESS_TOKEN": access_token}
            if refresh_token:
                env_vars_to_save["EBAY_USER_REFRESH_TOKEN"] = refresh_token
            _save_to_env(env_vars_to_save) # Attempt to save tokens anyway
        else: # No tokens, no details
            logging.error("Failed to obtain tokens, so cannot fetch user details or save credentials.")
            # No need to call _save_to_env here

        # Return based on success of getting tokens and user details, and saving them
        if access_token and user_id and user_name:
            # This path implies _save_to_env was attempted. We should check its result if critical.
            # For now, assume if we got here with details, it's mostly successful.
            return {"status": "success", "message": "Tokens and user details obtained.", "user_name": user_name}
        elif access_token: # Got tokens, but not full user details
            return {"status": "partial_success", "message": "Access token obtained, but user details incomplete."}
        else: # Failed to get access_token
            return {"status": "error", "message": "Failed to obtain access token during exchange."}

    except requests.exceptions.HTTPError as e:
        logging.error(f"HTTP error during token exchange: {e}")
        error_details = str(e)
        if e.response is not None:
            logging.error(f"Response content: {e.response.text}")
            error_details = e.response.text
        return {"status": "error", "message": "HTTP error during token exchange.", "error_details": error_details}
    except requests.exceptions.RequestException as e:
        logging.error(f"Request failed during token exchange: {e}")
        return {"status": "error", "message": "Request failed during token exchange.", "error_details": str(e)}
    except Exception as e:
        logging.error(f"An unexpected error occurred during token exchange: {e}")
        return {"status": "error", "message": "Unexpected error during token exchange.", "error_details": str(e)}

def initiate_user_login():
    """Initiates the full eBay OAuth2 user login flow."""
    logging.info("Initiating eBay user login process...")

    client_id = get_env_variable("EBAY_CLIENT_ID")
    # EBAY_RU_NAME is the *identifier* for your redirect URI configuration on eBay's side.
    # This is what you pass as the 'redirect_uri' parameter in the authorization request.
    ebay_ru_name = get_env_variable("EBAY_RU_NAME") 

    if not client_id or not ebay_ru_name:
        logging.error("EBAY_CLIENT_ID or EBAY_RU_NAME not found in .env. Cannot initiate login.")
        return {"status": "error", "message": "Configuration error: EBAY_CLIENT_ID or EBAY_RU_NAME missing."}

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
    logging.info(f"Generated scope string: '{auth_url_params['scope']}'") # Log the generated scope string
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
        return {"status": "error", "message": "Timeout waiting for eBay authorization callback."}
    
    server_thread.join(timeout=5) # Wait a bit for server thread to finish cleanly

    if auth_response.get('error'):
        error_details = auth_response['error']
        logging.error(f"Error during initial OAuth authorization: {error_details}")
        return {"status": "error", "message": "Error received from eBay during authorization.", "error_details": error_details}

    auth_code = auth_response.get('auth_code')
    received_state = auth_response.get('state')

    # TODO: Validate received_state against the oauth_state generated earlier
    # if received_state != oauth_state:
    #     logging.error("OAuth state mismatch. Possible CSRF attack.")
    #     return False
    # logging.info("OAuth state validated successfully.")

    if not auth_code:
        logging.error("No authorization code received from callback.")
        return {"status": "error", "message": "No authorization code received from eBay callback."}

    exchange_result = _exchange_auth_code_and_get_user_details(auth_code)

    if exchange_result.get("status") == "success":
        logging.info(f"Successfully obtained tokens and user details: {exchange_result.get('message')}")
        # Keep the print statements for direct script execution feedback
        print(f"\n--- eBay Login Successful ---")
        print(f"User Name: {exchange_result.get('user_name', 'N/A')}")
        print("Seller authentication state saved successfully.")
        print("-----------------------------")
    elif exchange_result.get("status") == "partial_success":
        logging.warning(f"eBay login partially successful: {exchange_result.get('message')}")
        print(f"\n--- eBay Login Partially Successful ---")
        print(f"{exchange_result.get('message')}")
        print("Available seller authentication state was saved.")
        print("-----------------------------")
    else: # Error case
        logging.error(f"Failed to obtain tokens or user details after authorization: {exchange_result.get('message')}")
        print(f"\n--- eBay Login Failed ---")
        print(f"Error: {exchange_result.get('message')}")
        if exchange_result.get('error_details'):
            print(f"Details: {exchange_result.get('error_details')}")
        print("-----------------------------")
    
    return exchange_result

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
        logging.info("Requesting a new access token from %s.", TOKEN_ENDPOINT)
        response = requests.post(TOKEN_ENDPOINT, data=payload, headers=headers)
        response.raise_for_status()
        token_data = response.json()
        new_access_token = token_data.get("access_token")

        if not new_access_token:
            logging.error("Failed to get new access token. No 'access_token' in response.")
            return None

        logging.info("Successfully refreshed access token.")
        
        new_refresh_token = token_data.get("refresh_token")
        
        env_vars_to_save = {"EBAY_USER_ACCESS_TOKEN": new_access_token}
        if new_refresh_token and new_refresh_token != current_refresh_token:
            logging.info("A rotated refresh token was received and will be saved.")
            env_vars_to_save["EBAY_USER_REFRESH_TOKEN"] = new_refresh_token
        elif new_refresh_token:
            logging.info("Refresh token re-issued but is the same as current. Not re-saving unless different.")
        else:
            logging.info("Refresh token was not re-issued during this refresh cycle.")

        _save_to_env(env_vars_to_save)
        return new_access_token

    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else "unknown"
        logging.error("eBay token refresh returned HTTP %s.", status)
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
    
    logging.info("Using the current access token to fetch user details.")
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
    parser = argparse.ArgumentParser(description="eBay authentication helper.")
    parser.add_argument("action", choices=["get_user", "refresh_token", "login"])
    parser.add_argument(
        "--env-path",
        "--env_path",
        dest="env_path",
        help="Optional path to a dotenv credentials file.",
    )
    args = parser.parse_args()

    if args.env_path:
        DOTENV_PATH = os.path.expanduser(args.env_path)
        if not os.path.isfile(DOTENV_PATH):
            parser.error(f"Credentials file not found: {DOTENV_PATH}")
        load_dotenv(DOTENV_PATH, override=True)

    if args.action == "login":
        result = initiate_user_login()
        if not result or result.get("status") not in {"success", "partial_success"}:
            raise SystemExit(1)
    elif args.action == "get_user":
        user_id, user_name = get_user_details()
        if not user_id or not user_name:
            print("Could not retrieve eBay user details. Check logs.")
            raise SystemExit(1)
        print(f"eBay user authenticated: {user_name} ({user_id})")
    else:
        if not refresh_access_token():
            print("Failed to refresh the eBay access token. Check logs.")
            raise SystemExit(1)
        print("eBay access token refreshed successfully.")
