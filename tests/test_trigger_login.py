import asyncio
import os
import sys
import logging
from dotenv import load_dotenv, set_key

# Add the src directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(env_path)

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def test_ebay_login():
    """
    Test function to trigger the eBay login flow directly using initiate_user_login.
    This will open a browser window for authentication.
    """
    from ebay_auth.ebay_auth import initiate_user_login
    
    print("=== Testing eBay Login ===")
    print("Initiating eBay login flow...")
    print("A browser window should open for you to authenticate with eBay.")
    print("After successful authentication, please restart the MCP server for the new tokens to take effect.")
    print("-" * 60)
    
    try:
        # Call the login function directly
        login_success = initiate_user_login()
        
        if login_success:
            print("\n=== Login Flow Completed Successfully ===")
            print("Your eBay tokens have been saved to the .env file.")
            print("\nIMPORTANT: Please restart the MCP server for the new tokens to take effect.")
            return True
        else:
            print("\n=== Login Flow Failed ===")
            print("Failed to complete the login process. Please check the logs for details.")
            return False
            
    except Exception as e:
        logger.error(f"Error during login test: {str(e)}", exc_info=True)
        return False

if __name__ == "__main__":
    # Run the test function
    test_ebay_login()
