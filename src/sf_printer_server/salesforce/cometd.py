import asyncio
import logging
import json
from typing import Optional, Callable
import aiohttp

logger = logging.getLogger(__name__)


class SalesforceCometD:
    """Salesforce Streaming API client using CometD protocol."""
    
    def __init__(self, endpoint, client_id, client_secret, username=None, access_token=None, instance_url=None):
        self.endpoint = endpoint
        self.client_id = client_id
        self.client_secret = client_secret
        self.username = username
        self.access_token = access_token
        self.instance_url = instance_url
        self.client_id = client_id
        self.event_handler: Optional[Callable] = None
        self.running = False
        self.session: Optional[aiohttp.ClientSession] = None
        self.client_id_counter = 0

    async def authenticate(self):
        """Authenticate with Salesforce."""
        # Authentication is already done, we have a token
        logger.info("Using pre-authenticated access token")
        
    async def subscribe_to_events(self, channel, handler):
        """Subscribe to a platform event channel using direct CometD protocol."""
        self.event_handler = handler
        
        logger.info(f"Subscribing to channel: {channel}")
        logger.info(f"Using instance URL: {self.instance_url}")
        logger.info(f"CometD endpoint: {self.endpoint}")
        logger.info(f"Access token (first 20 chars): {self.access_token[:20]}...")
        
        try:
            # Headers must be sent with EACH request, not just at session level
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                self.session = session
                
                # Handshake
                logger.info("Performing CometD handshake...")
                handshake_msg = [{
                    "channel": "/meta/handshake",
                    "version": "1.0",
                    "minimumVersion": "1.0",
                    "supportedConnectionTypes": ["long-polling"],
                    "id": str(self._next_id())
                }]
                
                async with session.post(self.endpoint, json=handshake_msg, headers=headers) as resp:
                    handshake_response = await resp.json()
                    logger.info(f"Handshake response: {handshake_response}")
                    
                    if not handshake_response[0].get("successful"):
                        error_msg = handshake_response[0].get("error", "Unknown error")
                        failure_reason = handshake_response[0].get("ext", {}).get("sfdc", {}).get("failureReason", "Unknown")
                        raise Exception(f"Handshake failed: {error_msg} (Reason: {failure_reason})")
                    
                    client_id = handshake_response[0]["clientId"]
                    logger.info(f"✓ Handshake successful, clientId: {client_id}")
                
                # Connect
                logger.info("Connecting to CometD...")
                connect_msg = [{
                    "channel": "/meta/connect",
                    "clientId": client_id,
                    "connectionType": "long-polling",
                    "id": str(self._next_id())
                }]
                
                async with session.post(self.endpoint, json=connect_msg, headers=headers) as resp:
                    connect_response = await resp.json()
                    logger.info(f"Connect response: {connect_response}")
                    
                    if not connect_response[0].get("successful"):
                        raise Exception(f"Connect failed: {connect_response[0]}")
                    
                    logger.info("✓ Connected to CometD")
                
                # Subscribe to channel
                logger.info(f"Subscribing to {channel}...")
                subscribe_msg = [{
                    "channel": "/meta/subscribe",
                    "clientId": client_id,
                    "subscription": channel,
                    "id": str(self._next_id())
                }]
                
                async with session.post(self.endpoint, json=subscribe_msg, headers=headers) as resp:
                    subscribe_response = await resp.json()
                    logger.info(f"Subscribe response: {subscribe_response}")
                    
                    if not subscribe_response[0].get("successful"):
                        raise Exception(f"Subscribe failed: {subscribe_response[0]}")
                    
                    logger.info(f"✓ Subscribed to channel: {channel}")
                
                # Long-polling loop to receive messages
                logger.info("Listening for events...")
                while self.running:
                    poll_msg = [{
                        "channel": "/meta/connect",
                        "clientId": client_id,
                        "connectionType": "long-polling",
                        "id": str(self._next_id())
                    }]
                    
                    try:
                        async with session.post(self.endpoint, json=poll_msg, headers=headers, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                            messages = await resp.json()
                            
                            for message in messages:
                                msg_channel = message.get("channel")
                                
                                # Handle data messages
                                if msg_channel == channel and "data" in message:
                                    logger.info(f"Received event on {channel}: {message['data']}")
                                    if self.event_handler:
                                        await self.handle_event(message["data"])
                                
                                # Log other message types
                                elif msg_channel and msg_channel.startswith("/meta/"):
                                    logger.debug(f"Meta message: {message}")
                    
                    except asyncio.TimeoutError:
                        logger.debug("Long-poll timeout, reconnecting...")
                        continue
                    except Exception as e:
                        logger.error(f"Poll error: {e}")
                        await asyncio.sleep(5)  # Wait before retry
                        
        except Exception as e:
            logger.error(f"Subscription error: {e}")
            logger.exception("Full traceback:")
            raise
    
    def _next_id(self):
        """Get next message ID."""
        self.client_id_counter += 1
        return self.client_id_counter

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
        if self.session:
            await self.session.close()
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