import asyncio
import logging
from typing import Optional, Callable
from aiosfstream import SalesforceStreamingClient

logger = logging.getLogger(__name__)


class SalesforceCometD:
    """Salesforce Streaming API client using CometD protocol."""
    
    def __init__(self, endpoint, client_id, client_secret, username=None, access_token=None):
        self.endpoint = endpoint
        self.client_id = client_id
        self.client_secret = client_secret
        self.username = username
        self.access_token = access_token
        self.client: Optional[SalesforceStreamingClient] = None
        self.event_handler: Optional[Callable] = None
        self.running = False

    async def authenticate(self):
        """Authenticate with Salesforce."""
        # Authentication is handled by the streaming client
        logger.info("Authenticating with Salesforce...")
        
    async def subscribe_to_events(self, channel, handler):
        """Subscribe to a platform event channel."""
        self.event_handler = handler
        
        if not self.client:
            # Create streaming client with access token
            self.client = SalesforceStreamingClient(
                consumer_key=self.client_id,
                consumer_secret=self.client_secret,
                access_token=self.access_token
            )
        
        logger.info(f"Subscribing to channel: {channel}")
        
        async with self.client:
            # Subscribe to the channel
            async for message in self.client.subscribe(channel):
                if self.event_handler and self.running:
                    await self.handle_event(message)
                elif not self.running:
                    break

    async def handle_event(self, event):
        """Process incoming event."""
        logger.info(f"Received event: {event}")
        if self.event_handler:
            if asyncio.iscoroutinefunction(self.event_handler):
                await self.event_handler(event)
            else:
                self.event_handler(event)

    async def start(self):
        """Start the CometD client."""
        self.running = True
        logger.info(f"Connected to CometD endpoint: {self.endpoint}")

    async def stop(self):
        """Stop the CometD client."""
        self.running = False
        if self.client:
            await self.client.close()
        logger.info(f"Disconnected from CometD endpoint: {self.endpoint}")


class CometDListener:
    """Legacy compatibility class."""
    
    def __init__(self, config):
        self.config = config
        self.cometd = None
        
    async def start(self):
        """Start listening for events."""
        self.cometd = SalesforceCometD(
            endpoint=self.config.get('salesforce.instance_url'),
            client_id=self.config.get('auth.client_id'),
            client_secret=self.config.get('auth.client_secret', ''),
            access_token=self.config.get('auth.access_token')
        )
        await self.cometd.start()
        
    async def stop(self):
        """Stop listening for events."""
        if self.cometd:
            await self.cometd.stop()