"""
Salesforce Pub/Sub API client implementation.

This module provides a client for subscribing to Salesforce platform events
using the gRPC-based Pub/Sub API.
"""
import logging
import json
import io
import threading
import xml.etree.ElementTree as et
from typing import Optional, Callable
from urllib.parse import urlparse
import requests
import grpc
import certifi

logger = logging.getLogger(__name__)

# These will be imported after stub generation
try:
    # Add the salesforce package to path so we can import the generated stubs
    import sys
    import os
    salesforce_dir = os.path.dirname(os.path.abspath(__file__))
    if salesforce_dir not in sys.path:
        sys.path.insert(0, salesforce_dir)
    
    import pubsub_api_pb2 as pb2
    import pubsub_api_pb2_grpc as pb2_grpc
    import avro.schema
    import avro.io
except ImportError as e:
    logger.warning(f"Stub files not found. Please run 'python scripts/generate_stubs.py' first. Error: {e}")
    pb2 = None
    pb2_grpc = None


def _soap_login(instance_url: str, username: str, password: str, api_version: str = "60.0"):
    """
    Authenticate via Salesforce SOAP API (username + password + security token).
    Returns (session_id, org_id, instance_url).
    This mirrors the official Salesforce Pub/Sub API Python example.
    """
    url_suffix = f"/services/Soap/u/{api_version}/"
    headers = {"content-type": "text/xml", "SOAPAction": "Login"}
    xml = (
        "<soapenv:Envelope xmlns:soapenv='http://schemas.xmlsoap.org/soap/envelope/' "
        "xmlns:xsi='http://www.w3.org/2001/XMLSchema-instance' "
        "xmlns:urn='urn:partner.soap.sforce.com'><soapenv:Body>"
        f"<urn:login><urn:username><![CDATA[{username}]]></urn:username>"
        f"<urn:password><![CDATA[{password}]]></urn:password>"
        "</urn:login></soapenv:Body></soapenv:Envelope>"
    )
    resp = requests.post(instance_url + url_suffix, data=xml, headers=headers)
    resp.raise_for_status()
    res_xml = et.fromstring(resp.content.decode("utf-8"))[0][0][0]

    url_parts = urlparse(res_xml[3].text)
    actual_instance_url = f"{url_parts.scheme}://{url_parts.netloc}"
    session_id = res_xml[4].text
    uinfo = res_xml[6]
    org_id = uinfo[8].text

    logger.info(f"SOAP login successful - org_id: {org_id}, instance_url: {actual_instance_url}")
    return session_id, org_id, actual_instance_url


class SalesforcePubSubClient:
    """Salesforce Pub/Sub API client using gRPC protocol."""
    
    PUBSUB_ENDPOINT = "api.pubsub.salesforce.com:7443"
    
    def __init__(self, access_token: str, instance_url: str, tenant_id: str):
        """
        Initialize the Pub/Sub API client.
        
        Args:
            access_token: Salesforce OAuth access token or SOAP session ID
            instance_url: Salesforce instance URL (e.g., https://mydomain.my.salesforce.com)
            tenant_id: Salesforce org ID (tenant ID)
        """
        if not pb2 or not pb2_grpc:
            raise ImportError(
                "gRPC stub files not found. Please run: python scripts/generate_stubs.py"
            )
        
        self.access_token = access_token
        self.instance_url = instance_url
        self.tenant_id = tenant_id
        self.event_handler: Optional[Callable] = None
        self.running = False
        self.channel: Optional[grpc.Channel] = None
        self.stub: Optional[pb2_grpc.PubSubStub] = None
        self.latest_replay_id: Optional[bytes] = None
        self.semaphore = threading.Semaphore(1)

    @classmethod
    def from_soap_auth(cls, username: str, password: str, instance_url: str, api_version: str = "60.0"):
        """
        Create a PubSubClient authenticated via SOAP login (username + password + security token).
        This is the method used by the official Salesforce Pub/Sub API example.
        
        Args:
            username: Salesforce username
            password: Password concatenated with security token (e.g., "MyPass123TokenABC")
            instance_url: Login URL (e.g., https://login.salesforce.com or https://test.salesforce.com)
            api_version: API version string
        """
        session_id, org_id, actual_instance_url = _soap_login(instance_url, username, password, api_version)
        return cls(
            access_token=session_id,
            instance_url=actual_instance_url,
            tenant_id=org_id
        )

    def _get_auth_metadata(self):
        """Get authentication metadata for gRPC calls."""
        return (
            ('accesstoken', self.access_token),
            ('instanceurl', self.instance_url),
            ('tenantid', self.tenant_id)
        )
    
    def _decode_event(self, schema_json: str, payload: bytes) -> dict:
        """
        Decode an Avro-encoded event payload.
        
        Args:
            schema_json: Avro schema in JSON format
            payload: Avro-encoded payload bytes
            
        Returns:
            Decoded event data as dict
        """
        schema = avro.schema.parse(schema_json)
        buf = io.BytesIO(payload)
        decoder = avro.io.BinaryDecoder(buf)
        reader = avro.io.DatumReader(schema)
        return reader.read(decoder)
    
    def _fetch_request_stream(self, topic: str, replay_preset=None, replay_id=None, num_requested: int = 1):
        """
        Generate FetchRequest stream for subscription.
        
        Args:
            topic: Topic name to subscribe to
            replay_preset: Replay preset (LATEST, EARLIEST, or CUSTOM)
            replay_id: Replay ID for CUSTOM preset
            num_requested: Number of events to request
            
        Yields:
            FetchRequest messages
        """
        # First request includes topic and replay settings
        first_request = True
        
        while self.running:
            self.semaphore.acquire()
            
            if first_request:
                request = pb2.FetchRequest(
                    topic_name=topic,
                    replay_preset=replay_preset or pb2.ReplayPreset.LATEST,
                    num_requested=num_requested
                )
                if replay_id:
                    request.replay_id = replay_id
                first_request = False
            else:
                # Subsequent requests don't need topic or replay settings
                request = pb2.FetchRequest(num_requested=num_requested)
            
            yield request
    
    def subscribe_to_events(self, channel: str, handler: Callable, num_requested: int = 1):
        """
        Subscribe to a platform event channel (synchronous/blocking).
        
        Args:
            channel: Event channel name (e.g., /event/Print_Job__e)
            handler: Callback function to handle incoming events (can be sync or async)
            num_requested: Number of events to request at a time (default: 1)
        """
        self.event_handler = handler
        self.running = True
        
        logger.info(f"Subscribing to channel: {channel}")
        logger.info(f"Using Pub/Sub API endpoint: {self.PUBSUB_ENDPOINT}")
        logger.info(f"Using instance URL: {self.instance_url}")
        logger.info(f"Tenant ID: {self.tenant_id}")
        
        try:
            # Set up SSL credentials
            with open(certifi.where(), 'rb') as f:
                creds = grpc.ssl_channel_credentials(f.read())
            
            auth_metadata = self._get_auth_metadata()
            logger.info(f"Auth metadata - instanceurl: {self.instance_url}")
            logger.info(f"Auth metadata - tenantid: {self.tenant_id}")
            logger.info(f"Auth metadata - accesstoken (first 20 chars): {self.access_token[:20]}...")
            
            # Create secure channel
            with grpc.secure_channel(self.PUBSUB_ENDPOINT, creds) as channel_conn:
                self.channel = channel_conn
                self.stub = pb2_grpc.PubSubStub(channel_conn)
                auth_metadata = self._get_auth_metadata()
                
                logger.info("✓ Connected to Pub/Sub API")

                # Call GetTopic first to verify permissions and log topic info
                try:
                    topic_info = self.stub.GetTopic(
                        pb2.TopicRequest(topic_name=channel),
                        metadata=auth_metadata
                    )
                    logger.info(f"GetTopic success - topic_name: {topic_info.topic_name}")
                    logger.info(f"GetTopic success - can_subscribe: {topic_info.can_subscribe}")
                    logger.info(f"GetTopic success - can_publish: {topic_info.can_publish}")
                    logger.info(f"GetTopic success - tenant_guid: {topic_info.tenant_guid}")
                    logger.info(f"GetTopic success - schema_id: {topic_info.schema_id}")
                    if not topic_info.can_subscribe:
                        raise RuntimeError(
                            f"Org reports can_subscribe=False for {channel}. "
                            "Check that the Platform Event exists and this user has subscribe permission."
                        )
                except grpc.RpcError as e:
                    logger.error(f"GetTopic failed: {e.code()}: {e.details()}")
                    raise

                logger.info("Listening for events...")
                
                # Subscribe to the channel
                subscription_stream = self.stub.Subscribe(
                    self._fetch_request_stream(channel, num_requested=num_requested),
                    metadata=auth_metadata
                )
                
                # Process incoming events (blocking loop)
                for fetch_response in subscription_stream:
                    if not self.running:
                        break
                    
                    # Release semaphore to allow next request
                    self.semaphore.release()
                    
                    # Store latest replay ID
                    self.latest_replay_id = fetch_response.latest_replay_id
                    
                    # Process events
                    if fetch_response.events:
                        logger.info(f"Received {len(fetch_response.events)} event(s)")
                        
                        for consumer_event in fetch_response.events:
                            try:
                                # Get the schema for decoding
                                schema_id = consumer_event.event.schema_id
                                schema_info = self.stub.GetSchema(
                                    pb2.SchemaRequest(schema_id=schema_id),
                                    metadata=auth_metadata
                                )
                                
                                # Decode the event payload
                                decoded_event = self._decode_event(
                                    schema_info.schema_json,
                                    consumer_event.event.payload
                                )
                                
                                logger.info(f"Decoded event: {json.dumps(decoded_event, indent=2)}")
                                
                                # Call the event handler (blocking)
                                if self.event_handler:
                                    self.event_handler(decoded_event)
                                
                            except Exception as e:
                                logger.error(f"Error processing event: {e}", exc_info=True)
                    else:
                        # Empty batch - keepalive message
                        logger.debug(f"Keepalive message received. Latest replay ID: {self.latest_replay_id}")
                        
        except grpc.RpcError as e:
            logger.error(f"gRPC error: {e.code()}: {e.details()}")
            raise
        except Exception as e:
            logger.error(f"Subscription error: {e}", exc_info=True)
            raise
        finally:
            self.running = False
            if self.channel:
                self.channel = None
    
    def start(self):
        """Start the Pub/Sub client."""
        self.running = True
        logger.info(f"Pub/Sub API client initialized")
    
    def stop(self):
        """Stop the Pub/Sub client."""
        self.running = False
        if self.channel:
            self.channel = None
        logger.info("Pub/Sub API client stopped")
