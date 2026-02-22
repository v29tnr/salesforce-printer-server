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
from sf_printer_server.salesforce.pubsub import SalesforcePubSubClient


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
        
        # Get org information
        instance_url = config.get('salesforce.instance_url')
        actual_instance_url = auth_manager.oauth_client.instance_url_from_token or instance_url
        
        # Get org ID (tenant ID) for Pub/Sub API
        logger.info("Retrieving org ID...")
        import aiohttp
        import json
        
        org_id = None
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Bearer {access_token}"}
                
                # Get org info from REST API
                identity_url = f"{actual_instance_url}/services/oauth2/userinfo"
                async with session.get(identity_url, headers=headers) as resp:
                    if resp.status == 200:
                        user_info = await resp.json()
                        org_id = user_info.get('organization_id')
                        logger.info(f"✓ Org ID: {org_id}")
                    else:
                        logger.error(f"Failed to get org ID: {resp.status}")
                        
        except Exception as e:
            logger.error(f"Error retrieving org ID: {e}")
            sys.exit(1)
        
        if not org_id:
            logger.error("Could not retrieve org ID. Please check authentication.")
            sys.exit(1)
        
        # For Pub/Sub API, we can use any valid OAuth token (JWT, Web OAuth, etc.)
        # Unlike Streaming API (CometD), Pub/Sub API works with all token types
        logger.info("Initializing Pub/Sub API client...")
        
        pubsub_client = SalesforcePubSubClient(
            access_token=access_token,
            instance_url=actual_instance_url,
            tenant_id=org_id
        )
        
        await pubsub_client.start()
        
        # Subscribe to platform events
        # TODO: Get event name from config or Salesforce metadata
        event_channel = "/event/Print_Job__e"
        logger.info(f"Subscribing to: {event_channel}")
        
        async def handle_print_job(event):
            """Handle incoming print job events."""
            logger.info(f"Received print job: {event}")
            # TODO: Process print job and send to printer
        
        # Keep running and listening for events
        await pubsub_client.subscribe_to_events(event_channel, handle_print_job)
        
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