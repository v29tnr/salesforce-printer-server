"""
Authentication setup and management utilities.
Simplifies configuration for different authentication methods.
"""

import logging
from pathlib import Path
from typing import Optional
from sf_printer_server.auth.oauth import SalesforceOAuthClient
from sf_printer_server.config.manager import ConfigManager

logger = logging.getLogger(__name__)


class AuthManager:
    """Manages authentication configuration and setup."""
    
    def __init__(self, config_manager: ConfigManager):
        """
        Initialize authentication manager.
        
        Args:
            config_manager: Configuration manager instance
        """
        self.config = config_manager
        self.oauth_client: Optional[SalesforceOAuthClient] = None
        
    def initialize(self) -> bool:
        """
        Initialize OAuth client from configuration.
        
        Returns:
            True if successful
        """
        try:
            auth_method = self.config.get('auth.method', 'jwt')
            client_id = self.config.get('auth.client_id')
            instance_url = self.config.get('salesforce.instance_url')
            
            if not client_id:
                logger.error("No client_id configured. Run 'sf-printer-server config set-auth' first.")
                return False
            
            if not instance_url:
                logger.error("No instance_url configured.")
                return False
            
            # Initialize OAuth client
            client_secret = self.config.get('auth.client_secret', '')
            redirect_uri = self.config.get('auth.redirect_uri', 'http://localhost:8888/oauth/callback')
            
            self.oauth_client = SalesforceOAuthClient(
                client_id=client_id,
                client_secret=client_secret,
                instance_url=instance_url,
                redirect_uri=redirect_uri
            )
            
            # Authenticate based on method
            if auth_method == 'jwt':
                return self._authenticate_jwt()
            elif auth_method == 'password':
                return self._authenticate_password()
            elif auth_method == 'web':
                return self._authenticate_web()
            else:
                logger.error(f"Unknown auth method: {auth_method}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to initialize authentication: {e}")
            return False
    
    def _authenticate_jwt(self) -> bool:
        """Authenticate using JWT Bearer flow."""
        username = self.config.get('auth.username')
        private_key_file = self.config.get('auth.private_key_file')
        
        if not username or not private_key_file:
            logger.error("JWT authentication requires 'username' and 'private_key_file' in config")
            return False
        
        if not Path(private_key_file).exists():
            logger.error(f"Private key file not found: {private_key_file}")
            return False
        
        logger.info(f"Authenticating via JWT as {username}")
        return self.oauth_client.authenticate_jwt_bearer(username, private_key_file)
    
    def _authenticate_password(self) -> bool:
        """Authenticate using username-password flow."""
        username = self.config.get('auth.username')
        # Support both 'password' and 'streaming_password' config keys
        password = self.config.get('auth.password') or self.config.get('auth.streaming_password')
        
        if not username or not password:
            logger.error("Password authentication requires 'username' and 'password' (or 'streaming_password') in config")
            return False
        
        logger.info(f"Authenticating via password flow as {username}")
        return self.oauth_client.authenticate_client_credentials(username, password)
    
    def _authenticate_web(self) -> bool:
        """Authenticate using web server flow."""
        # Check if we already have a valid token
        if self.oauth_client.is_token_valid():
            logger.info("Already authenticated with valid token")
            return True
        
        # Try to refresh if we have a refresh token
        if self.oauth_client.refresh_token:
            logger.info("Attempting to refresh access token")
            if self.oauth_client.refresh_access_token():
                return True
        
        # Need to do interactive login
        logger.info("Starting interactive authentication")
        return self.oauth_client.authenticate_web_server_flow()
    
    def get_access_token(self) -> Optional[str]:
        """
        Get current access token, refreshing if needed.
        
        Returns:
            Access token or None
        """
        if not self.oauth_client:
            logger.error("OAuth client not initialized")
            return None
        
        return self.oauth_client.get_access_token()
    
    def test_authentication(self) -> bool:
        """
        Test if authentication is working by making a test API call.
        
        Returns:
            True if authentication successful
        """
        try:
            token = self.get_access_token()
            if not token:
                logger.error("Failed to get access token")
                return False
            
            # Make a simple API call to verify token works
            import requests
            
            instance_url = self.oauth_client.instance_url_from_token or self.config.get('salesforce.instance_url')
            api_version = self.config.get('salesforce.api_version', '60.0')
            
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(
                f"{instance_url}/services/data/v{api_version}/",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info("✓ Authentication test successful")
                logger.info(f"✓ Connected to: {instance_url}")
                logger.info(f"✓ API Version: {api_version}")
                return True
            else:
                logger.error(f"Authentication test failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Authentication test failed: {e}")
            return False
    
    def logout(self):
        """Revoke tokens and clear credentials."""
        if self.oauth_client:
            self.oauth_client.revoke_token()
            logger.info("Logged out successfully")


def setup_jwt_auth(
    config_manager: ConfigManager,
    client_id: str,
    username: str,
    private_key_file: str,
    instance_url: str = "https://login.salesforce.com"
):
    """
    Configure JWT authentication.
    
    Args:
        config_manager: Configuration manager
        client_id: Connected App Consumer Key
        username: Integration user username
        private_key_file: Path to private key file
        instance_url: Salesforce instance URL
    """
    config_manager.set('auth.method', 'jwt')
    config_manager.set('auth.client_id', client_id)
    config_manager.set('auth.username', username)
    config_manager.set('auth.private_key_file', private_key_file)
    config_manager.set('salesforce.instance_url', instance_url)
    config_manager.save()
    
    logger.info("JWT authentication configured successfully")


def setup_password_auth(
    config_manager: ConfigManager,
    client_id: str,
    client_secret: str,
    username: str,
    password: str,
    instance_url: str = "https://login.salesforce.com"
):
    """
    Configure username-password authentication.
    
    Args:
        config_manager: Configuration manager
        client_id: Connected App Consumer Key
        client_secret: Connected App Consumer Secret
        username: Integration user username
        password: Password + Security Token
        instance_url: Salesforce instance URL
    """
    config_manager.set('auth.method', 'password')
    config_manager.set('auth.client_id', client_id)
    config_manager.set('auth.client_secret', client_secret)
    config_manager.set('auth.username', username)
    config_manager.set('auth.password', password)
    config_manager.set('salesforce.instance_url', instance_url)
    config_manager.save()
    
    logger.info("Password authentication configured successfully")


def setup_web_auth(
    config_manager: ConfigManager,
    client_id: str,
    client_secret: str,
    instance_url: str = "https://login.salesforce.com",
    redirect_uri: str = "http://localhost:8888/oauth/callback"
):
    """
    Configure web server flow authentication.
    
    Args:
        config_manager: Configuration manager
        client_id: Connected App Consumer Key
        client_secret: Connected App Consumer Secret
        instance_url: Salesforce instance URL
        redirect_uri: OAuth callback URL
    """
    config_manager.set('auth.method', 'web')
    config_manager.set('auth.client_id', client_id)
    config_manager.set('auth.client_secret', client_secret)
    config_manager.set('auth.redirect_uri', redirect_uri)
    config_manager.set('salesforce.instance_url', instance_url)
    config_manager.save()
    
    logger.info("Web authentication configured successfully")
