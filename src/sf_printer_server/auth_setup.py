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
        
        # Update config to use web auth method
        config_path = config.config_file
        print(f"Note: Update your config to use 'method = \"web\"' in {config_path}")
        print("      (Or keep JWT for REST API and use this token for Streaming)")
        
        return True
    else:
        print()
        print("❌ Authentication failed.")
        print("   Make sure your Connected App has:")
        print("   • Callback URL: http://localhost:8888/oauth/callback")
        print("   • OAuth Scopes: Full access (full)")
        print("   • IP Relaxation: Relax IP restrictions")
        return False


if __name__ == '__main__':
    success = authenticate()
    sys.exit(0 if success else 1)
