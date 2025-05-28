# Description:
# Script to acquire an eBay authentication token via OAuth.
# Sets up a light weight server that listens on port 9292 for the OAuth callback.
# Setup a Cloudflare redirect tunnel and set redirect URL in eBay RuName to point to the Cloudflare redirect tunnel.
# Usage:
# 
# For automatic mode:
#   python ebay_authentication_token.py --mode auto
# 
# To use a different port, e.g., 8080:
#   python ebay_authentication_token.py --mode auto --port 8080
# 
# For manual mode (or by default):
#   python ebay_authentication_token.py or python ebay_authentication_token.py --mode manual

import os
from dotenv import load_dotenv, set_key
import requests
from base64 import b64encode
from urllib.parse import urlparse, parse_qs
import webbrowser
import argparse
import threading
import http.server
import socketserver
import queue

# Global queue to pass authorization code/error from HTTP server thread to main thread
auth_response_queue = queue.Queue()
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
            auth_response_queue.put({'code': query_params['code'][0]})
            self.wfile.write(b"<html><body><h1>Authorization code received.</h1><p>You can close this browser tab.</p></body></html>")
            print("\nAuthorization code received by local server.")
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
        default="manual", 
        help="'manual': paste redirect URL. 'auto': use local HTTP server for redirect (default: manual)."
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
    load_dotenv()

    client_id = os.getenv("EBAY_CLIENT_ID")
    client_secret = os.getenv("EBAY_CLIENT_SECRET")
    # This redirect_uri is the one registered with eBay (e.g., https://ebayauth.petetreadaway.com)
    redirect_uri_registered = os.getenv("EBAY_REDIRECT_URI") 

    if not all([client_id, client_secret, redirect_uri_registered]):
        print("Error: EBAY_CLIENT_ID, EBAY_CLIENT_SECRET, or EBAY_REDIRECT_URI not found in .env file.")
        exit()

    scopes = (
        "https://api.ebay.com/oauth/api_scope "
        "https://api.ebay.com/oauth/api_scope/sell.inventory "
        "https://api.ebay.com/oauth/api_scope/commerce.identity.readonly"
    )
    consent_endpoint_production = "https://auth.ebay.com/oauth2/authorize"
    token_endpoint = "https://api.ebay.com/identity/v1/oauth2/token"

    consent_url = (
        f"{consent_endpoint_production}?"
        f"client_id={client_id}&"
        f"redirect_uri={redirect_uri_registered}&"
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
            if 'code' in response_from_server:
                authorization_code = response_from_server['code']
            elif 'error' in response_from_server:
                error_details_from_redirect = response_from_server['error']
                print(f"Error from OAuth redirect: {error_details_from_redirect}")
        except queue.Empty:
            print("\nTimeout: No authorization response received from local server within 5 minutes.")
            if http_server_instance: # Attempt to shutdown server if it's still running
                print("Attempting to shutdown local server due to timeout...")
                threading.Thread(target=http_server_instance.shutdown).start()
            exit()
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
                exit()
        except Exception as e:
            print(f"Error parsing the authorization code URL: {e}")
            exit()

    if error_details_from_redirect:
        print(f"OAuth process failed. Error details: {error_details_from_redirect}")
        exit()

    if not authorization_code:
        print("Error: Authorization code not obtained.")
        exit()

    print(f"\nAuthorization Code: {authorization_code[:10]}... (shortened for display)")

    # Make the authorization code grant request to obtain the token
    payload = {
        "grant_type": "authorization_code",
        "code": authorization_code,
        "redirect_uri": redirect_uri_registered # Must match the redirect_uri used in consent request
    }
    credentials = f"{client_id}:{client_secret}"
    encoded_credentials = b64encode(credentials.encode()).decode()
    token_headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {encoded_credentials}"
    }

    try:
        response = requests.post(token_endpoint, headers=token_headers, data=payload)
        response.raise_for_status()
        response_json = response.json()
        print("\nResponse containing the User access token and refresh token:")
        print(response_json)

        access_token = response_json.get("access_token")
        refresh_token = response_json.get("refresh_token")
        expires_in = response_json.get("expires_in")
        refresh_token_expires_in = response_json.get("refresh_token_expires_in")

        if access_token and refresh_token:
            env_file_path = ".env"
            try:
                set_key(env_file_path, "EBAY_OAUTH_TOKEN", access_token)
                set_key(env_file_path, "EBAY_REFRESH_TOKEN", refresh_token)
                print(f"\nSuccessfully updated {env_file_path} with new tokens.")
            except Exception as e:
                print(f"\nError updating {env_file_path}: {e}")

            print("\n--- Token Summary ---")
            if len(access_token) > 20:
                print(f"Access Token:   {access_token[:10]}...{access_token[-10:]}")
            else:
                print(f"Access Token:   {access_token}")
            if len(refresh_token) > 20:
                print(f"Refresh Token:  {refresh_token[:10]}...{refresh_token[-10:]}")
            else:
                print(f"Refresh Token:  {refresh_token}")
            print("---------------------")
        else:
            print("\nError: Could not retrieve access_token or refresh_token. .env file not updated.")

        print(f"Access Token Expires In (seconds): {expires_in}")
        print(f"Refresh Token Expires In (seconds): {refresh_token_expires_in}")

    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
        print(f"Response content: {response.text if response else 'No response object'}")
    except requests.exceptions.RequestException as req_err:
        print(f"Request error occurred: {req_err}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        if 'response' in locals() and hasattr(response, 'text'):
            print(f"Response content: {response.text}")

if __name__ == "__main__":
    main()
