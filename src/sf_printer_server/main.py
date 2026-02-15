"""
Main entry point for Salesforce Printer Server.
Starts the server to listen for platform events and process print jobs.
"""
import sys
import asyncio
import logging
import signal
from pathlib import Path
from sf_printer_server.config.manager import ConfigManager
from sf_printer_server.auth.manager import AuthManager
from sf_printer_server.salesforce.cometd import SalesforceCometD


def setup_logging(config: ConfigManager):
    """Configure logging based on config settings."""
    level = config.get('logging.level', 'INFO')
    logging.basicConfig(
        level=getattr(logging, level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


async def start_server():
    """Start the printer server."""
    logger = logging.getLogger(__name__)
    
    try:
        # Load configuration
        logger.info("Loading configuration...")
        config = ConfigManager()
        setup_logging(config)
        
        # Check if configured
        if not config.exists():
            logger.error("Server not configured. Please run the installer first.")
            logger.error("Run: python -m sf_printer_server.installer")
            sys.exit(1)
        
        # Initialize authentication
        logger.info("Initializing authentication...")
        auth_manager = AuthManager(config)
        if not auth_manager.initialize():
            logger.error("Authentication failed. Please check your configuration.")
            sys.exit(1)
        
        access_token = auth_manager.get_access_token()
        logger.info("✓ Authentication successful")
        
        # Verify token works with a test API call
        instance_url = config.get('salesforce.instance_url')
        actual_instance_url = auth_manager.oauth_client.instance_url_from_token or instance_url
        
        logger.info("Testing API access with token...")
        import aiohttp
        import json
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Bearer {access_token}"}
                
                # Test REST API
                test_url = f"{actual_instance_url}/services/data/v57.0/"
                async with session.get(test_url, headers=headers) as resp:
                    if resp.status == 200:
                        logger.info("✓ Token valid for REST API")
                    else:
                        logger.warning(f"REST API test returned status {resp.status}: {await resp.text()}")
                
                # Decode JWT to see what's inside
                import base64
                try:
                    token_parts = access_token.split('.')
                    if len(token_parts) >= 2:
                        # Decode payload (add padding if needed)
                        payload = token_parts[1]
                        payload += '=' * (4 - len(payload) % 4)
                        decoded = json.loads(base64.b64decode(payload))
                        logger.info(f"JWT scopes: {decoded.get('scope', 'No scope field in JWT')}")
                        logger.info(f"JWT sub: {decoded.get('sub', 'N/A')}")
                        logger.info(f"JWT aud: {decoded.get('aud', 'N/A')}")
                except Exception as e:
                    logger.debug(f"Could not decode JWT: {e}")
                    
        except Exception as e:
            logger.error(f"Token test failed: {e}")
        
        # Initialize CometD client
        logger.info("Connecting to Salesforce Streaming API...")
        client_id = config.get('auth.client_id')
        
        cometd = SalesforceCometD(
            endpoint=f"{actual_instance_url}/cometd/57.0",
            client_id=client_id,
            client_secret=config.get('auth.client_secret', ''),
            access_token=access_token,
            instance_url=actual_instance_url
        )
        
        await cometd.start()
        
        # Subscribe to platform events
        # TODO: Get event name from config or Salesforce metadata
        event_channel = "/event/Print_Job__e"
        logger.info(f"Subscribing to: {event_channel}")
        
        async def handle_print_job(event):
            """Handle incoming print job events."""
            logger.info(f"Received print job: {event}")
            # TODO: Process print job and send to printer
        
        # Keep running and listening for events
        await cometd.subscribe_to_events(event_channel, handle_print_job)
        
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)


def main():
    """Main entry point."""
    # Run the async server
    try:
        asyncio.run(start_server())
    except KeyboardInterrupt:
        print("\nServer stopped.")
        sys.exit(0)


if __name__ == "__main__":
    main()