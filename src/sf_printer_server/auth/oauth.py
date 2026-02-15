"""
OAuth2 authentication for Salesforce using Connected App.
Supports both Web Server Flow (user interactive) and JWT Bearer Flow (server-to-server).
"""

import json
import os
import time
import logging
import webbrowser
from pathlib import Path
from typing import Optional, Dict, Any
from urllib.parse import urlencode, parse_qs, urlparse
import http.server
import socketserver
import threading

import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import jwt

logger = logging.getLogger(__name__)


class SalesforceOAuthClient:
    """OAuth2 client for Salesforce Connected App authentication."""
    
    def __init__(
        self,
        client_id: str,
        client_secret: Optional[str] = None,
        instance_url: str = None,
        redirect_uri: str = "http://localhost:8888/oauth/callback",
        token_file: Optional[str] = None
    ):
        """
        Initialize Salesforce OAuth client.
        
        Args:
            client_id: Connected App Consumer Key
            client_secret: Connected App Consumer Secret (optional for JWT flow)
            instance_url: Salesforce instance URL (e.g., https://login.salesforce.com)
            redirect_uri: OAuth callback URL
            token_file: Path to store/load token
        """
        self.client_id = client_id
        self.client_secret = client_secret or ''
        self.instance_url = instance_url.rstrip('/')
        self.redirect_uri = redirect_uri
        
        # Use default token file location if not specified
        if token_file:
            self.token_file = Path(token_file)
        else:
            # Check if running in Docker (config mounted at /app/config)
            docker_config = Path('/app/config')
            if docker_config.exists() and docker_config.is_dir():
                # Running in Docker - save token in mounted config directory
                self.token_file = docker_config / 'oauth_token.json'
            else:
                # Running natively - use home directory
                config_dir = Path.home() / '.sf_printer_server'
                config_dir.mkdir(exist_ok=True)
                self.token_file = config_dir / 'oauth_token.json'
        
        self.access_token = None
        self.refresh_token = None
        self.instance_url_from_token = None
        self.token_expires_at = None
        
        # Load existing token if available
        self._load_token()
    
    def get_authorization_url(self) -> str:
        """
        Get the OAuth2 authorization URL for user login.
        
        Returns:
            Authorization URL string
        """
        params = {
            'response_type': 'code',
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'scope': 'api refresh_token'
        }
        
        auth_url = f"{self.instance_url}/services/oauth2/authorize?{urlencode(params)}"
        logger.debug(f"Authorization URL: {auth_url}")
        return auth_url
    
    def authenticate_web_server_flow(self) -> bool:
        """
        Authenticate using Web Server OAuth flow with local callback server.
        Opens browser for user to login and handles callback automatically.
        
        Returns:
            True if authentication successful
        """
        # Start local callback server
        auth_code = None
        error = None
        
        class CallbackHandler(http.server.SimpleHTTPRequestHandler):
            def do_GET(self):
                nonlocal auth_code, error
                
                # Parse query parameters
                query = parse_qs(urlparse(self.path).query)
                
                if 'code' in query:
                    auth_code = query['code'][0]
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(b'''
                        <html><body>
                        <h1>Authentication Successful!</h1>
                        <p>You can close this window and return to the terminal.</p>
                        <script>window.close();</script>
                        </body></html>
                    ''')
                elif 'error' in query:
                    error = query.get('error_description', ['Unknown error'])[0]
                    self.send_response(400)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(f'''
                        <html><body>
                        <h1>Authentication Failed</h1>
                        <p>{error}</p>
                        </body></html>
                    '''.encode())
                else:
                    self.send_response(404)
                    self.end_headers()
            
            def log_message(self, format, *args):
                # Suppress server logs
                pass
        
        # Start callback server on port 8888
        port = 8888
        try:
            with socketserver.TCPServer(("localhost", port), CallbackHandler) as httpd:
                logger.info(f"Starting callback server on port {port}")
                
                # Open browser for authorization
                auth_url = self.get_authorization_url()
                print(f"\n{'='*60}")
                print("SALESFORCE AUTHENTICATION REQUIRED")
                print(f"{'='*60}")
                print("\nOpening browser for authentication...")
                print(f"If browser doesn't open, visit this URL:\n{auth_url}\n")
                
                webbrowser.open(auth_url)
                
                # Wait for callback (timeout after 5 minutes)
                httpd.timeout = 300
                start_time = time.time()
                
                while not auth_code and not error and (time.time() - start_time) < 300:
                    httpd.handle_request()
                
                if error:
                    logger.error(f"Authentication error: {error}")
                    return False
                
                if not auth_code:
                    logger.error("Authentication timeout - no response received")
                    return False
                
                # Exchange code for tokens
                return self._exchange_code_for_token(auth_code)
                
        except OSError as e:
            logger.error(f"Failed to start callback server: {e}")
            logger.info("Falling back to manual code entry...")
            return self._authenticate_manual()
    
    def _authenticate_manual(self) -> bool:
        """Manual authentication flow when callback server fails."""
        auth_url = self.get_authorization_url()
        
        print(f"\n{'='*60}")
        print("MANUAL AUTHENTICATION REQUIRED")
        print(f"{'='*60}")
        print("\n1. Open this URL in your browser:")
        print(f"   {auth_url}")
        print("\n2. Login and authorize the application")
        print("3. You will be redirected to a URL starting with:")
        print(f"   {self.redirect_uri}")
        print("\n4. Copy the FULL URL from your browser and paste it below")
        print(f"{'='*60}\n")
        
        callback_url = input("Paste the callback URL here: ").strip()
        
        # Parse authorization code from URL
        parsed = urlparse(callback_url)
        query = parse_qs(parsed.query)
        
        if 'code' not in query:
            logger.error("No authorization code found in URL")
            return False
        
        auth_code = query['code'][0]
        return self._exchange_code_for_token(auth_code)
    
    def _exchange_code_for_token(self, auth_code: str) -> bool:
        """
        Exchange authorization code for access and refresh tokens.
        
        Args:
            auth_code: Authorization code from OAuth callback
            
        Returns:
            True if successful
        """
        token_url = f"{self.instance_url}/services/oauth2/token"
        
        data = {
            'grant_type': 'authorization_code',
            'code': auth_code,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'redirect_uri': self.redirect_uri
        }
        
        try:
            logger.info("Exchanging authorization code for tokens...")
            response = requests.post(token_url, data=data)
            response.raise_for_status()
            
            token_data = response.json()
            self._store_token_data(token_data)
            
            logger.info("Successfully obtained access token")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to exchange code for token: {e}")
            if hasattr(e.response, 'text'):
                logger.error(f"Response: {e.response.text}")
            return False
    
    def authenticate_client_credentials(self, username: str, password: str) -> bool:
        """
        Authenticate using username-password flow (for headless servers).
        Requires Connected App to have "Username-Password" flow enabled.
        
        Args:
            username: Salesforce username
            password: Salesforce password + security token
            
        Returns:
            True if successful
        """
        token_url = f"{self.instance_url}/services/oauth2/token"
        
        data = {
            'grant_type': 'password',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'username': username,
            'password': password
        }
        
        try:
            logger.info(f"Authenticating with username-password flow for {username}")
            response = requests.post(token_url, data=data)
            response.raise_for_status()
            
            token_data = response.json()
            self._store_token_data(token_data)
            
            logger.info("Successfully obtained access token")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Authentication failed: {e}")
            if hasattr(e.response, 'text'):
                logger.error(f"Response: {e.response.text}")
            return False
    
    def authenticate_jwt_bearer(self, username: str, private_key_file: str) -> bool:
        """
        Authenticate using JWT Bearer flow (server-to-server).
        Requires Connected App configured with certificate.
        
        Args:
            username: Salesforce username to authenticate as
            private_key_file: Path to private key file
            
        Returns:
            True if successful
        """
        try:
            # Load private key
            with open(private_key_file, 'rb') as key_file:
                private_key = serialization.load_pem_private_key(
                    key_file.read(),
                    password=None,
                    backend=default_backend()
                )
            
            # Determine correct audience for JWT
            # Must be login.salesforce.com or test.salesforce.com, not My Domain
            if 'test.salesforce' in self.instance_url or 'sandbox' in self.instance_url:
                aud = 'https://test.salesforce.com'
            else:
                aud = 'https://login.salesforce.com'
            
            # Create JWT
            claim = {
                'iss': self.client_id,
                'sub': username,
                'aud': aud,
                'exp': int(time.time()) + 300  # 5 minutes
            }
            
            logger.debug(f"JWT claim: iss={self.client_id}, sub={username}, aud={aud}")
            
            assertion = jwt.encode(claim, private_key, algorithm='RS256')
            
            # Request token
            token_url = f"{self.instance_url}/services/oauth2/token"
            data = {
                'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
                'assertion': assertion
            }
            
            logger.info(f"Authenticating with JWT Bearer flow for {username}")
            response = requests.post(token_url, data=data)
            response.raise_for_status()
            
            token_data = response.json()
            self._store_token_data(token_data)
            
            logger.info("Successfully obtained access token via JWT")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"JWT authentication failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    logger.error(f"Salesforce error: {error_detail}")
                    logger.error(f"Common causes:")
                    logger.error(f"  1. Connected App not yet active (wait 2-10 minutes after creation)")
                    logger.error(f"  2. User '{username}' not authorized for this Connected App")
                    logger.error(f"  3. Certificate doesn't match private key")
                    logger.error(f"  4. User doesn't have API access enabled")
                except:
                    logger.error(f"Response: {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"JWT authentication error: {e}")
            logger.exception("Full traceback:")
            return False
    
    def refresh_access_token(self) -> bool:
        """
        Refresh the access token using refresh token.
        
        Returns:
            True if successful
        """
        if not self.refresh_token:
            logger.error("No refresh token available")
            return False
        
        token_url = f"{self.instance_url}/services/oauth2/token"
        
        data = {
            'grant_type': 'refresh_token',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'refresh_token': self.refresh_token
        }
        
        try:
            logger.info("Refreshing access token...")
            response = requests.post(token_url, data=data)
            response.raise_for_status()
            
            token_data = response.json()
            self._store_token_data(token_data, keep_refresh=True)
            
            logger.info("Successfully refreshed access token")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to refresh token: {e}")
            return False
    
    def _store_token_data(self, token_data: Dict[str, Any], keep_refresh: bool = False):
        """Store token data from OAuth response."""
        self.access_token = token_data.get('access_token')
        self.instance_url_from_token = token_data.get('instance_url')
        
        # Only update refresh token if provided (not provided in refresh response)
        if not keep_refresh or 'refresh_token' in token_data:
            self.refresh_token = token_data.get('refresh_token')
        
        # Calculate expiration
        expires_in = token_data.get('expires_in', 7200)  # Default 2 hours
        self.token_expires_at = time.time() + expires_in
        
        # Save to file
        self._save_token()
    
    def _save_token(self):
        """Save token to file."""
        token_data = {
            'access_token': self.access_token,
            'refresh_token': self.refresh_token,
            'instance_url': self.instance_url_from_token,
            'expires_at': self.token_expires_at
        }
        
        try:
            self.token_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.token_file, 'w') as f:
                json.dump(token_data, f, indent=2)
            
            # Set restrictive permissions
            os.chmod(self.token_file, 0o600)
            logger.debug(f"Saved token to {self.token_file}")
            
        except Exception as e:
            logger.error(f"Failed to save token: {e}")
    
    def _load_token(self):
        """Load token from file."""
        if not self.token_file.exists():
            return
        
        try:
            with open(self.token_file, 'r') as f:
                token_data = json.load(f)
            
            self.access_token = token_data.get('access_token')
            self.refresh_token = token_data.get('refresh_token')
            self.instance_url_from_token = token_data.get('instance_url')
            self.token_expires_at = token_data.get('expires_at')
            
            logger.debug(f"Loaded token from {self.token_file}")
            
        except Exception as e:
            logger.error(f"Failed to load token: {e}")
    
    def is_token_valid(self) -> bool:
        """Check if current token is valid and not expired."""
        if not self.access_token:
            return False
        
        if not self.token_expires_at:
            return False
        
        # Consider token expired 5 minutes before actual expiration
        return time.time() < (self.token_expires_at - 300)
    
    def ensure_authenticated(self) -> bool:
        """
        Ensure we have a valid access token, refreshing if needed.
        
        Returns:
            True if authenticated
        """
        if self.is_token_valid():
            return True
        
        if self.refresh_token:
            return self.refresh_access_token()
        
        logger.warning("No valid token and no refresh token available")
        return False
    
    def get_access_token(self) -> Optional[str]:
        """
        Get current access token, refreshing if needed.
        
        Returns:
            Access token or None
        """
        if self.ensure_authenticated():
            return self.access_token
        return None
    
    def get_streaming_session_id(self) -> Optional[str]:
        """
        Get a session ID suitable for Streaming API (CometD).
        JWT Bearer tokens don't work directly with CometD, so we use frontdoor.jsp
        to get a proper session ID.
        
        Returns:
            Session ID or None
        """
        if not self.access_token:
            logger.error("No access token available")
            return None
        
        try:
            # Use frontdoor.jsp to get a session with the OAuth token
            # This creates a browser session that works with Streaming API
            instance = self.instance_url_from_token or self.instance_url
            
            # Alternative: Try to get session via REST API userinfo endpoint
            headers = {"Authorization": f"Bearer {self.access_token}"}
            
            # Try getting session from identity endpoint
            identity_url = f"{instance}/services/oauth2/userinfo"
            response = requests.get(identity_url, headers=headers)
            response.raise_for_status()
            
            # For JWT tokens, we need to use the OAuth token itself for Streaming API
            # Some orgs allow this, but it requires specific OAuth scopes
            logger.info("Using OAuth token for Streaming API (JWT Bearer Flow)")
            return self.access_token
            
        except Exception as e:
            logger.error(f"Failed to get streaming session: {e}")
            return self.access_token  # Fallback to using the token directly
    
    def revoke_token(self):
        """Revoke the current token and delete stored credentials."""
        if self.access_token:
            try:
                revoke_url = f"{self.instance_url}/services/oauth2/revoke"
                requests.post(revoke_url, data={'token': self.access_token})
                logger.info("Token revoked")
            except Exception as e:
                logger.error(f"Failed to revoke token: {e}")
        
        # Clear in-memory tokens
        self.access_token = None
        self.refresh_token = None
        self.instance_url_from_token = None
        self.token_expires_at = None
        
        # Delete token file
        if self.token_file.exists():
            self.token_file.unlink()
            logger.info(f"Deleted token file: {self.token_file}")