"""
Main entry point for Salesforce Printer Server.
"""
import sys
import asyncio
import logging
from sf_printer_server.config.manager import ConfigManager
from sf_printer_server.salesforce.pubsub import SalesforcePubSubClient
from sf_printer_server.salesforce.context import set_sf_credentials
from sf_printer_server.jobs.processor import process_event


def setup_logging(config: ConfigManager):
    level = config.get('logging.level', 'INFO')
    logging.basicConfig(
        level=getattr(logging, level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


async def start_server():
    logger = logging.getLogger(__name__)

    try:
        config = ConfigManager()
        setup_logging(config)

        if not config.exists():
            logger.error("Server not configured. Run: sf-printer-server setup")
            sys.exit(1)

        instance_url = config.get('salesforce.instance_url', '').rstrip('/')
        client_id = config.get('auth.client_id', '')
        client_secret = config.get('auth.client_secret', '')

        if not all([instance_url, client_id, client_secret]):
            logger.error("Missing required config: salesforce.instance_url, auth.client_id, auth.client_secret")
            sys.exit(1)

        logger.info("Authenticating via OAuth Client Credentials flow...")
        pubsub_client = SalesforcePubSubClient.from_client_credentials(
            client_id=client_id,
            client_secret=client_secret,
            login_url=instance_url,
        )

        # Store credentials in shared context so the processor can
        # auto-inject Bearer auth when downloading Salesforce content URLs.
        set_sf_credentials(
            pubsub_client.access_token,
            pubsub_client.instance_url,
            client_id=client_id,
            client_secret=client_secret,
        )

        event_channel = config.get('salesforce.platform_event_channel', '/event/SF_Printer_Event__e')
        logger.info(f"Subscribing to: {event_channel}")

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            pubsub_client.subscribe_to_events,
            event_channel,
            process_event,
        )

    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)


def main():
    try:
        asyncio.run(start_server())
    except KeyboardInterrupt:
        print("\nServer stopped.")
        sys.exit(0)


if __name__ == "__main__":
    main()
