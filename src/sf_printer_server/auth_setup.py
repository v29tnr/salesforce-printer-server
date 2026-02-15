#!/usr/bin/env python3
"""
Interactive authentication setup for Salesforce Printer Server.
Uses Web Server OAuth flow (browser-based) to get tokens that work with Streaming API.
No security token required!
"""

import sys
import logging
from pathlib import Path
from sf_printer_server.config.manager import ConfigManager
from sf_printer_server.auth.oauth import SalesforceOAuthClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def authenticate_manual():
    """Manual OAuth for headless/SSH environments."""
    print("\n" + "="*60)
    print("  Manual OAuth Authentication (Headless Mode)")
    print("="*60 + "\n")
    
    config = ConfigManager()
    client_id = config.get('auth.client_id')
    instance_url = config.get('salesforce.instance_url')
    
    oauth_client = SalesforceOAuthClient(
        client_id=client_id,
        client_secret='',
        instance_url=instance_url,
        redirect_uri='http://localhost:8888/oauth/callback'
    )
    
    auth_url = oauth_client.get_authorization_url()
    
    print("Since you're in a headless environment, follow these steps:")
    print()
    print("1. Open this URL in a browser ON YOUR LOCAL MACHINE:")
    print()
    print(f"   {auth_url}")
    print()
    print("2. Log in to Salesforce")
    print()
    print("3. You'll be redirected to a URL like:")
    print("   http://localhost:8888/oauth/callback?code=XXXXXXXXX")
    print()
    print("4. Copy the 'code' parameter value (the part after 'code=')")
    print()
    
    auth_code = input("Paste the authorization code here: ").strip()
    
    if not auth_code:
        print("❌ No code provided")
        return False
    
    print("\n🔄 Exchanging code for access token...")
    
    if oauth_client.exchange_code_for_token(auth_code):
        print()
        print("✅ Authentication successful!")
        print("Token saved and will work with Streaming API!")
        return True
    else:
        print("❌ Failed to exchange code for token")
        return False


def authenticate_password():
    """Password + Security Token authentication."""
    print("\n" + "="*60)
    print("  Username-Password OAuth Authentication")
    print("="*60 + "\n")
    
    config = ConfigManager()
    client_id = config.get('auth.client_id')
    instance_url = config.get('salesforce.instance_url')
    username = config.get('auth.username')
    
    print("This method requires your password + security token.")
    print()
    print("Get your security token:")
    print("  Salesforce Setup → My Personal Information → Reset My Security Token")
    print("  (Will be emailed to you)")
    print()
    
    if not username:
        username = input("Username: ").strip()
    else:
        print(f"Username: {username}")
    
    import getpass
    password = getpass.getpass("Password: ")
    security_token = input("Security Token: ").strip()
    
    full_password = password + security_token
    
    oauth_client = SalesforceOAuthClient(
        client_id=client_id,
        client_secret='',
        instance_url=instance_url
    )
    
    print("\n🔄 Authenticating...")
    
    if oauth_client.authenticate_client_credentials(username, full_password):
        print()
        print("✅ Authentication successful!")
        print("Token saved and will work with Streaming API!")
        return True
    else:
        print("❌ Authentication failed")
        return False


def authenticate():
    """Run interactive OAuth authentication."""
    print("\n" + "="*60)
    print("  Salesforce Printer Server - Authentication Setup")
    print("="*60 + "\n")
    
    # Load config
    config = ConfigManager()
    if not config.exists():
        print("❌ Configuration not found. Run the installer first:")
        print("   ./install.sh")
        sys.exit(1)
    
    client_id = config.get('auth.client_id')
    instance_url = config.get('salesforce.instance_url')
    
    if not client_id:
        print("❌ No client_id configured. Run the installer first.")
        sys.exit(1)
    
    print(f"Instance: {instance_url}")
    print(f"Client ID: {client_id[:20]}...")
    print()
    
    # Check if running in SSH/headless environment
    import os
    display_available = os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')
    ssh_connection = os.environ.get('SSH_CONNECTION') or os.environ.get('SSH_CLIENT')
    
    if ssh_connection and not display_available:
        print("🖥️  Detected headless/SSH environment")
        print()
        print("Choose authentication method:")
        print("  1. Manual OAuth (recommended - paste code from browser)")
        print("  2. Username-Password (requires security token)")
        print("  3. Try browser anyway (if X11 forwarding enabled)")
        print()
        choice = input("Enter choice [1-3]: ").strip()
        
        if choice == '1':
            return authenticate_manual()
        elif choice == '2':
            return authenticate_password()
        elif choice == '3':
            pass  # Continue to browser flow below
        else:
            print("Invalid choice")
            return False
    
    # Initialize OAuth client for web flow
    oauth_client = SalesforceOAuthClient(
        client_id=client_id,
        client_secret='',  # Not required for web flow
        instance_url=instance_url,
        redirect_uri='http://localhost:8888/oauth/callback'
    )
    
    print("🌐 Starting browser-based authentication...")
    print("   This will open your browser to log in to Salesforce.")
    print("   The token obtained will work with Streaming API!")
    print()
    
    # Authenticate using web server flow
    if oauth_client.authenticate_web_server_flow():
        print()
        print("✅ Authentication successful!")
        print()
        print("Token saved. You can now start the server:")
        print("   make start")
        print()
        
        return True
    else:
        print()
        print("❌ Authentication failed.")
        print("   Try manual method instead: run this script again and choose option 1")
        return False


if __name__ == '__main__':
    success = authenticate()
    sys.exit(0 if success else 1)
