import asyncio
import logging
from typing import Optional, Callable
from aiocometd import Client as CometDClient
from aiocometd.extensions import Extension

logger = logging.getLogger(__name__)


class BearerTokenAuthExtension(Extension):
    """Auth extension that adds Bearer token to requests."""
    
    def __init__(self, access_token):
        self.access_token = access_token
    
    async def outgoing(self, payload, headers):
        """Add authorization header to outgoing requests."""
        headers["Authorization"] = f"Bearer {self.access_token}"
    
    async def incoming(self, payload, headers=None):
        """Process incoming messages (no-op for this extension)."""
        pass


class SalesforceCometD:
    """Salesforce Streaming API client using CometD protocol."""
    
    def __init__(self, endpoint, client_id, client_secret, username=None, access_token=None, instance_url=None):
        self.endpoint = endpoint
        self.client_id = client_id
        self.client_secret = client_secret
        self.username = username
        self.access_token = access_token
        self.instance_url = instance_url
        self.client: Optional[CometDClient] = None
        self.event_handler: Optional[Callable] = None
        self.running = False

    async def authenticate(self):
        """Authenticate with Salesforce."""
        # Authentication is handled by the streaming client
        logger.info("Authenticating with Salesforce...")
        
    async def subscribe_to_events(self, channel, handler):
        """Subscribe to a platform event channel."""
        self.event_handler = handler
        
        logger.info(f"Subscribing to channel: {channel}")
        logger.info(f"Using instance URL: {self.instance_url}")
        logger.info(f"CometD endpoint: {self.endpoint}")
        
        try:
            # Create auth extension with our access token
            auth_extension = BearerTokenAuthExtension(self.access_token)
            
            # Create CometD client with auth extension
            client = CometDClient(
                self.endpoint,
                extensions=[auth_extension]
            )
            
            async with client:
                logger.info("Successfully connected to CometD endpoint")
                
                # Subscribe to the channel
                await client.subscribe(channel)
                logger.info(f"Subscribed to channel: {channel}")
                
                # Listen for messages
                async for message in client:
                    logger.debug(f"Raw message received: {message}")
                    
                    # Check if this is a data message for our channel
                    if message.get("channel") == channel and "data" in message:
                        event_data = message["data"]
                        logger.info(f"Event data: {event_data}")
                        
                        if self.event_handler and self.running:
                            await self.handle_event(event_data)
                        elif not self.running:
                            break
                        
        except Exception as e:
            logger.error(f"Subscription error: {e}")
            logger.exception("Full traceback:")
            raise

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