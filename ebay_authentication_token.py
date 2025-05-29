import os
from dotenv import load_dotenv, set_key, find_dotenv
import requests
from base64 import b64encode
from urllib.parse import urlparse, parse_qs
import webbrowser
import argparse
import sys
import threading
import http.server
import socketserver
import queue

# Global queue to pass authorization code/error from HTTP server thread to main thread
auth_response_queue = queue.Queue()

# --- Global Configuration (populated by main) ---
CLIENT_ID_GLOBAL = None
CLIENT_SECRET_GLOBAL = None
REDIRECT_URI_REGISTERED_GLOBAL = None
TOKEN_ENDPOINT_GLOBAL = "https://api.ebay.com/identity/v1/oauth2/token"
USER_API_ENDPOINT_GLOBAL = "https://apiz.ebay.com/commerce/identity/v1/user/"
# --- End Global Configuration ---
# Global variable to hold the server instance for shutdown
http_server_instance = None

# --- Local HTTP Server for OAuth Callback ---
class OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_response_queue, http_server_instance
        parsed_path = urlparse(self.path)
        query_params = parse_qs(parsed_path.query)

        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()

        if 'code' in query_params:
            auth_code = query_params['code'][0]
            print(f"\nAuthorization code received by local server: {auth_code[:10]}...")

            result = _exchange_code_and_get_user(auth_code)
            print(result)
            html_content = ""
            if result.get("error"):
                error_message = result["error"]
                details = result.get("details", "No additional details.")
                print(f"Error during token exchange or user info fetch: {error_message}. Details: {details}")
                auth_response_queue.put({'error': error_message, 'details': str(details)})
                # Ensure details are stringified for HTML
                html_details = str(details).replace('<', '&lt;').replace('>', '&gt;') # Basic HTML escaping
                html_content = f"""<html><head><title>eBay Auth Error</title></head><body>
                                    <h1>Authentication Failed</h1>
                                    <p><b>Error:</b> {error_message}</p>
                                    <p><b>Details:</b> <pre>{html_details}</pre></p>
                                    <p>Please check the console output and try again.</p>
                                    </body></html>"""
            else:
                user_id = result["user_id"]
                user_name = result["user_name"]
                auth_response_queue.put(result) # Put the whole dict with tokens and user_id
                html_content = f"""<html><head><title>eBay Auth Success</title></head><body>
                                    <h1>Authentication Successful!</h1>
                                    <p>Logged in as eBay User: <b>{user_name}</b></p>
                                    <p>eBay UserID: <b>{user_id}</b></p>
                                    <p>Access token and refresh token have been processed.</p>
                                    <p>You can now close this browser tab.</p>
                                    </body></html>"""
                print(f"\nSuccessfully processed authentication for eBay User:")
                print(f"User Name: {user_name}")
                print(f"User ID: {user_id}")

            
            self.wfile.write(html_content.encode('utf-8'))
            print("\nAuthorization process complete in handler. Signalling main thread.")
        elif 'error' in query_params:
            error_details = {k: v[0] for k, v in query_params.items()}
            auth_response_queue.put({'error': error_details})
            self.wfile.write(b"<html><body><h1>Error during authorization.</h1><p>Check the console output.</p></body></html>")
            print(f"\nError received by local server: {error_details}")
        else:
            auth_response_queue.put({'error': {'unknown': 'No code or error in query params'}})
            self.wfile.write(b"<html><body><h1>Unknown response.</h1><p>Check the console output.</p></body></html>")
            print("\nUnknown response received by local server.")

        # Shutdown the server in a new thread to allow this request to complete
        if http_server_instance:
            threading.Thread(target=http_server_instance.shutdown).start()

    def log_message(self, format, *args):
        # Suppress most log messages to keep console clean, but allow error logging
        if "error" in format.lower() or (args and any("error" in str(arg).lower() for arg in args)):
            super().log_message(format, *args)
        elif "info" in format.lower() or (args and any("info" in str(arg).lower() for arg in args)):
             # Optionally log specific info messages if needed, e.g., server start/stop
            if "server" in format.lower() or (args and any("server" in str(arg).lower() for arg in args)):
                 super().log_message(format, *args)
        # else: pass to suppress other messages like GET requests

# --- Helper function to exchange code and get user ID ---
def _exchange_code_and_get_user(auth_code):
    # Uses CLIENT_ID_GLOBAL, CLIENT_SECRET_GLOBAL, REDIRECT_URI_REGISTERED_GLOBAL, TOKEN_ENDPOINT_GLOBAL, USER_API_ENDPOINT_GLOBAL
    payload = {
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": REDIRECT_URI_REGISTERED_GLOBAL
    }
    auth_header_val = f"{CLIENT_ID_GLOBAL}:{CLIENT_SECRET_GLOBAL}"
    auth_header = b64encode(auth_header_val.encode()).decode()
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {auth_header}"
    }
    try:
        # 1. Exchange code for token
        print(f"\nExchanging authorization code for token at {TOKEN_ENDPOINT_GLOBAL}...")
        response = requests.post(TOKEN_ENDPOINT_GLOBAL, data=payload, headers=headers)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        token_data = response.json()
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")

        if not access_token:
            print("Error: Access token not found in eBay response.")
            return {"error": "Access token not found in eBay response."}
        print(f"Access token received: {access_token[:10]}...")
        if refresh_token:
            print(f"Refresh token received: {refresh_token[:10]}...")

        # 2. Get user ID using the access token
        print(f"\nFetching user information from {USER_API_ENDPOINT_GLOBAL}...")
        user_headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }
        user_response = requests.get(USER_API_ENDPOINT_GLOBAL, headers=user_headers)
        user_response.raise_for_status()
        user_data = user_response.json()
        print(user_data)
        user_id = user_data.get("userId") # Using userId as requested
        user_name = user_data.get("username")

        if not user_id:
            print("Error: eBay UserID (userId) not found in user API response.")
            # Still return tokens if we got them, as they might be useful
            return {"error": "eBay UserID (userId) not found in user API response.", "access_token": access_token, "refresh_token": refresh_token}
        print(f"eBay UserID received: {user_id}")

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user_id": user_id,
            "user_name": user_name,
            "error": None
        }
    except requests.exceptions.HTTPError as e:
        error_message = f"HTTP error during eBay API call: {e}"
        details = "No response content available."
        if e.response is not None:
            try:
                details = e.response.json() # Try to get JSON error details
            except ValueError: # JSONDecodeError is a subclass of ValueError
                details = e.response.text # Fallback to raw text
        print(f"{error_message}\nDetails: {details}")
        return {"error": error_message, "details": details}
    except requests.exceptions.RequestException as e:
        error_message = f"Request failed during eBay API call: {e}"
        print(error_message)
        return {"error": error_message}
    except Exception as e:
        error_message = f"An unexpected error occurred: {e}"
        print(error_message)
        return {"error": error_message}


def start_local_http_server(port, callback_path_segment):
    global http_server_instance
    # The handler is instantiated for each request, so it doesn't need callback_path_segment directly
    # We rely on the external setup to forward to http://localhost:port/callback_path_segment
    try:
        http_server_instance = socketserver.TCPServer(("localhost", port), OAuthCallbackHandler)
        print(f"\nLocal HTTP server started on http://localhost:{port}{callback_path_segment}")
        print("Waiting for eBay to redirect to your configured RuName, which should forward here...")
        http_server_instance.serve_forever()
        print("Local HTTP server stopped.")
    except Exception as e:
        print(f"\nError starting local HTTP server: {e}")
        auth_response_queue.put({'error': {'server_error': str(e)}})
    finally:
        if http_server_instance:
            http_server_instance.server_close() # Ensure socket is closed

def main():
    parser = argparse.ArgumentParser(description="Fetch eBay OAuth tokens.")
    parser.add_argument(
        "--mode", 
        choices=["manual", "auto"], 
        default="auto",  # Changed default to auto
        help="'manual': paste redirect URL. 'auto': use local HTTP server for redirect (default: auto)."
    )
    parser.add_argument(
        "--port", 
        type=int, 
        default=9292, 
        help="Port for local HTTP server in 'auto' mode (default: 9292)."
    )
    args = parser.parse_args()

    LOCAL_SERVER_CALLBACK_PATH = "/oauth/callback" # Fixed path for the local listener

    # Load environment variables from .env file
    # Determine .env path. Prefer script's directory, then project root, then CWD.
    script_dir = os.path.dirname(os.path.abspath(__file__))
    dotenv_path = os.path.join(script_dir, '.env')

    if not os.path.exists(dotenv_path):
        project_root = os.path.dirname(script_dir) # Assumes script is in a subdir of project root
        dotenv_path_project_root = os.path.join(project_root, '.env')
        if os.path.exists(dotenv_path_project_root):
            dotenv_path = dotenv_path_project_root
        else:
            # Fallback for scripts not in a typical project structure or if .env is elsewhere
            found_dotenv = find_dotenv(usecwd=True, raise_error_if_not_found=False)
            if found_dotenv:
                dotenv_path = found_dotenv
            else:
                # Default to creating/using .env in CWD if not found anywhere sensible
                dotenv_path = os.path.join(os.getcwd(), ".env")
    
    print(f"Using .env path: {dotenv_path}")
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path)
        print(f".env file loaded from {dotenv_path}")
    else:
        print(f"Warning: .env file not found at {dotenv_path}. Will attempt to create if tokens are fetched.")

    global CLIENT_ID_GLOBAL, CLIENT_SECRET_GLOBAL, REDIRECT_URI_REGISTERED_GLOBAL
    CLIENT_ID_GLOBAL = os.getenv("EBAY_CLIENT_ID")
    CLIENT_SECRET_GLOBAL = os.getenv("EBAY_CLIENT_SECRET")
    REDIRECT_URI_REGISTERED_GLOBAL = os.getenv("EBAY_REDIRECT_URI")

    client_id = os.getenv("EBAY_CLIENT_ID")
    client_secret = os.getenv("EBAY_CLIENT_SECRET")
    # This redirect_uri is the one registered with eBay (e.g., https://ebayauth.petetreadaway.com)
    redirect_uri_registered = os.getenv("EBAY_REDIRECT_URI") 

    if not all([CLIENT_ID_GLOBAL, CLIENT_SECRET_GLOBAL, REDIRECT_URI_REGISTERED_GLOBAL]):
        print("Error: EBAY_CLIENT_ID, EBAY_CLIENT_SECRET, or EBAY_REDIRECT_URI not found in environment.")
        print(f"Please ensure they are set in your .env file ({dotenv_path}) or environment variables.")
        sys.exit(1)

    scopes = (
        "https://api.ebay.com/oauth/api_scope "
        "https://api.ebay.com/oauth/api_scope/sell.inventory "
        "https://api.ebay.com/oauth/api_scope/commerce.identity.readonly"
    )
    consent_endpoint_production = "https://auth.ebay.com/oauth2/authorize"
    token_endpoint = "https://api.ebay.com/identity/v1/oauth2/token"

    consent_url = (
        f"{consent_endpoint_production}?"
        f"client_id={CLIENT_ID_GLOBAL}&"
        f"redirect_uri={REDIRECT_URI_REGISTERED_GLOBAL}&"
        f"response_type=code&"
        f"scope={scopes}"
    )

    authorization_code = None
    error_details_from_redirect = None

    if args.mode == "auto":
        print(f"\n--- Auto Mode: Using local HTTP server on port {args.port} ---")
        print(f"Ensure your eBay RuName ('{redirect_uri_registered}') redirects to http://localhost:{args.port}{LOCAL_SERVER_CALLBACK_PATH}")
        
        server_thread = threading.Thread(target=start_local_http_server, args=(args.port, LOCAL_SERVER_CALLBACK_PATH))
        server_thread.daemon = True # Allow main program to exit even if server thread is alive
        server_thread.start()

        webbrowser.open(consent_url)
        print("\nOpening browser for eBay consent. Please grant consent.")
        print(f"If browser doesn't open, manually navigate to: {consent_url}")

        try:
            # Wait for the auth code or error from the server thread
            print("Waiting for authorization response from local server...")
            response_from_server = auth_response_queue.get(timeout=300) # 5 minutes timeout
            # The queue now sends a dictionary with 'access_token', 'refresh_token', 'user_id', or 'error'
            if response_from_server.get('error'):
                error_details_from_redirect = response_from_server['error']
                details = response_from_server.get('details', '')
                print(f"Error from OAuth process: {error_details_from_redirect}. Details: {details}")
                # No authorization_code to process if error occurred in handler's exchange logic
                authorization_code = None 
            elif response_from_server.get('access_token'):
                # Tokens and user_id were successfully fetched by the handler
                access_token = response_from_server['access_token']
                refresh_token = response_from_server.get('refresh_token')
                user_id = response_from_server['user_id']
                print(f"\nTokens and UserID ({user_id}) received from handler.")
                
                # Save tokens to .env
                # Use the determined dotenv_path for consistency
                print(f"Saving tokens to: {dotenv_path}")
                set_key(dotenv_path, "EBAY_OAUTH_TOKEN", access_token)
                print(f"Successfully set EBAY_OAUTH_TOKEN in {dotenv_path}")
                if refresh_token:
                    set_key(dotenv_path, "EBAY_OAUTH_REFRESH_TOKEN", refresh_token)
                    print(f"Successfully set EBAY_OAUTH_REFRESH_TOKEN in {dotenv_path}")
                set_key(dotenv_path, "USE_ENV_OAUTH_TOKEN", "True")
                print(f"Set USE_ENV_OAUTH_TOKEN to True in {dotenv_path}")
                print(f"\nSuccessfully obtained and saved tokens. eBay UserID: {user_id}")
                print("You can now use MCP tools that require user authentication.")
                sys.exit(0) # Successful completion
            else:
                # Should not happen if queue contract is followed by handler
                error_details_from_redirect = {'unknown_handler_response': 'Unexpected response from handler'}
                print(f"Error: {error_details_from_redirect}")
        except queue.Empty:
            print("\nTimeout: No authorization response received from local server within 5 minutes.")
            if http_server_instance: # Attempt to shutdown server if it's still running
                print("Attempting to shutdown local server due to timeout...")
                threading.Thread(target=http_server_instance.shutdown).start()
            sys.exit(1)
        finally:
            # Ensure server thread is joined if it was started
            if server_thread.is_alive():
                if http_server_instance: # Check again, might have been shut down by handler
                    # If server is still up, means timeout or other issue before handler shutdown
                    if not auth_response_queue.empty(): # Check if something came in last moment
                        pass # Already handled or will be handled
                    else:
                        print("Shutting down local server thread...")
                        # Ensure server is shut down before trying to join
                        if hasattr(http_server_instance, 'is_serving') and http_server_instance.is_serving():
                             threading.Thread(target=http_server_instance.shutdown).start()
                server_thread.join(timeout=5) # Wait for server thread to finish
                if server_thread.is_alive():
                    print("Warning: Local server thread did not terminate cleanly.")

    elif args.mode == "manual":
        print("\n--- Manual Mode ---")
        webbrowser.open(consent_url)
        print("\nOpening browser for eBay consent. Please grant consent.")
        print(f"If browser doesn't open, manually navigate to: {consent_url}")
        authorization_code_url = input("After granting consent, paste the entire redirect URL here: ")
        try:
            parsed_url = urlparse(authorization_code_url)
            query_params = parse_qs(parsed_url.query)
            if 'code' in query_params:
                authorization_code = query_params['code'][0]
            elif 'error' in query_params:
                error_details_from_redirect = {k: v[0] for k, v in query_params.items()}
                print(f"Error from OAuth redirect: {error_details_from_redirect}")
            else:
                print("Error: 'code' or 'error' not found in the pasted redirect URL.")
                sys.exit(1)
        except Exception as e:
            print(f"Error parsing the authorization code URL: {e}")
            sys.exit(1)

    # If we reach here in 'auto' mode, it means the handler put an error on the queue, or timeout occurred.
    # If 'manual' mode, we proceed to exchange code if obtained.

    if args.mode == "manual":
        if error_details_from_redirect:
            print(f"OAuth process failed. Error details: {error_details_from_redirect}")
            sys.exit(1)
        if not authorization_code:
            print("Error: Authorization code not obtained in manual mode.")
            sys.exit(1)

        print(f"\nAuthorization Code (manual mode): {authorization_code[:10]}...")
        # In manual mode, the main thread does the exchange and user ID fetch
        result = _exchange_code_and_get_user(authorization_code)
        if result.get("error"):
            error_message = result["error"]
            details = result.get("details", "")
            print(f"Error during token exchange or user info fetch (manual mode): {error_message}. Details: {details}")
            sys.exit(1)
        else:
            access_token = result['access_token']
            refresh_token = result.get('refresh_token')
            user_id = result['user_id']
            
            print(f"Saving tokens to: {dotenv_path}")
            set_key(dotenv_path, "EBAY_OAUTH_TOKEN", access_token)
            print(f"Successfully set EBAY_OAUTH_TOKEN in {dotenv_path}")
            if refresh_token:
                set_key(dotenv_path, "EBAY_OAUTH_REFRESH_TOKEN", refresh_token)
                print(f"Successfully set EBAY_OAUTH_REFRESH_TOKEN in {dotenv_path}")
            set_key(dotenv_path, "USE_ENV_OAUTH_TOKEN", "True")
            print(f"Set USE_ENV_OAUTH_TOKEN to True in {dotenv_path}")
            print(f"\nTokens saved successfully (manual mode). eBay UserID: {user_id}")
            print("You can now use MCP tools that require user authentication.")
    elif error_details_from_redirect: # Handles errors from auto mode that were put on queue by handler
        print(f"OAuth process failed (auto mode). Error details: {error_details_from_redirect}")
        sys.exit(1)
    # If timeout occurred in auto mode, message already printed.
    # Script will exit after main finishes if it falls through here.
    return 0 # Explicitly return 0 for successful fall-through if no exit paths were taken

if __name__ == "__main__":

    main()
