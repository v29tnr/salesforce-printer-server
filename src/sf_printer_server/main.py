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
        
        # Initialize CometD client
        logger.info("Connecting to Salesforce Streaming API...")
        instance_url = config.get('salesforce.instance_url')
        client_id = config.get('auth.client_id')
        
        cometd = SalesforceCometD(
            endpoint=f"{instance_url}/cometd/57.0",
            client_id=client_id,
            client_secret=config.get('auth.client_secret', ''),
            access_token=access_token
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