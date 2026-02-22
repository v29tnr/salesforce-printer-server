# Pub/Sub API Migration Guide

## Overview

The Salesforce Printer Server has been migrated from the legacy CometD Streaming API to the modern **Pub/Sub API**. The Pub/Sub API is a gRPC-based API that provides better performance, reliability, and broader authentication support.

## Key Benefits

### Why Pub/Sub API?

1. **Better Performance**: gRPC/HTTP2-based for efficient binary message delivery
2. **Universal Token Support**: Works with ALL OAuth token types (JWT, Web OAuth, Username-Password)
3. **Modern Protocol**: Uses Protocol Buffers (Avro) for efficient serialization
4. **Better Flow Control**: Pull-based subscription with client-controlled flow
5. **Improved Reliability**: Automatic keepalives and better error handling

### Comparison: CometD vs Pub/Sub API

| Feature | CometD (Old) | Pub/Sub API (New) |
|---------|--------------|-------------------|
| Protocol | HTTP/1.1 Long-polling | gRPC/HTTP2 Streaming |
| Authentication | ❌ JWT not supported | ✅ All OAuth types supported |
| Performance | Slower | Faster |
| Flow Control | Server-push | Client-controlled pull |
| Binary Format | JSON | Avro (Protocol Buffers) |
| Keepalive | Manual | Automatic |

## Setup Instructions

### Prerequisites

- Python 3.8 or later
- pip package manager
- Internet access to download dependencies

### Installation Steps

#### 1. Install Dependencies

Run the setup script to install all required dependencies and generate gRPC stub files:

**Windows (PowerShell):**
```powershell
.\scripts\setup_pubsub.ps1
```

**Linux/Mac:**
```bash
chmod +x scripts/setup_pubsub.sh
./scripts/setup_pubsub.sh
```

**Manual Installation:**
```bash
# Install Python dependencies
pip install grpcio grpcio-tools avro-python3 certifi requests

# Generate gRPC stub files
python scripts/generate_stubs.py
```

#### 2. Verify Installation

The setup script generates two stub files in `src/sf_printer_server/salesforce/`:
- `pubsub_api_pb2.py` - Protocol Buffer definitions
- `pubsub_api_pb2_grpc.py` - gRPC client/server code

#### 3. Run the Server

```bash
python -m sf_printer_server.main
```

## Authentication

The Pub/Sub API works with **all** OAuth token types:

### ✅ Supported Authentication Methods

1. **JWT Bearer Flow** (Server-to-Server)
   - Best for automated processes
   - No user interaction required
   - Works with Pub/Sub API!

2. **Web Server OAuth Flow** (Browser-based)
   - For interactive applications
   - Run `./auth-setup.sh` to configure

3. **Username-Password Flow**
   - Add `streaming_password` to config
   - Password + security token

All methods work equally well with Pub/Sub API. Choose based on your security requirements.

## Configuration

No configuration changes needed! The server automatically uses Pub/Sub API with your existing authentication setup.

### Config File (config.toml)

```toml
[auth]
client_id = "your_connected_app_client_id"
client_secret = "your_client_secret"  # If using Web OAuth
username = "user@example.com"  # If using JWT or Username-Password
private_key_file = "path/to/server.key"  # If using JWT

[salesforce]
instance_url = "https://yourdomain.my.salesforce.com"
```

## API Reference

### SalesforcePubSubClient

Main client class for subscribing to events.

```python
from sf_printer_server.salesforce.pubsub import SalesforcePubSubClient

# Initialize client
client = SalesforcePubSubClient(
    access_token="your_access_token",
    instance_url="https://yourdomain.my.salesforce.com",
    tenant_id="your_org_id"
)

# Start client
await client.start()

# Subscribe to events
async def handle_event(event):
    print(f"Received event: {event}")

await client.subscribe_to_events(
    channel="/event/Print_Job__e",
    handler=handle_event,
    num_requested=1  # Number of events to request at a time
)
```

### Event Channels

Platform event channel formats:

- **Custom Platform Event**: `/event/EventName__e`
- **Standard Platform Event**: `/event/EventName`
- **Change Data Capture (All)**: `/data/ChangeEvents`
- **Change Data Capture (Single Object)**: `/data/ObjectName__ChangeEvent`
- **Custom Channel**: `/event/CustomChannel__chn`

## Troubleshooting

### Stub Files Not Found

If you see errors about missing `pubsub_api_pb2` or `pubsub_api_pb2_grpc`:

```bash
python scripts/generate_stubs.py
```

### gRPC Connection Errors

1. **Firewall**: Ensure `api.pubsub.salesforce.com:7443` is allowed
2. **SSL Certificate**: Requires valid SSL certificates (uses certifi package)
3. **Authentication**: Verify your access token is valid

### No Events Received

1. **Check Event Definition**: Verify event exists in Salesforce
2. **Check Permissions**: Ensure user has permission to subscribe to the event
3. **Publish Test Event**: Manually publish an event to test

### Authentication Errors

```
Error: UNAUTHENTICATED
```

**Solutions:**
- Verify access token is not expired
- Check instance URL matches your org
- Verify org ID (tenant ID) is correct

## Migration from CometD

### What Changed?

1. **Import Statement**:
   ```python
   # Old
   from sf_printer_server.salesforce.cometd import SalesforceCometD
   
   # New
   from sf_printer_server.salesforce.pubsub import SalesforcePubSubClient
   ```

2. **Client Initialization**:
   ```python
   # Old
   client = SalesforceCometD(
       endpoint=f"{instance_url}/cometd/57.0",
       client_id=client_id,
       access_token=token,
       instance_url=instance_url
   )
   
   # New
   client = SalesforcePubSubClient(
       access_token=token,
       instance_url=instance_url,
       tenant_id=org_id
   )
   ```

3. **Authentication**: No more special "streaming_password" workaround needed!

### What Stayed the Same?

- Event channel names (e.g., `/event/Print_Job__e`)
- Event handler interface
- Configuration file structure

## Advanced Features

### Replay ID Support

Resume subscriptions from a specific point:

```python
# Get latest replay ID
replay_id = client.latest_replay_id

# Resume from saved replay ID
await client.subscribe_to_events(
    channel="/event/Print_Job__e",
    handler=handle_event,
    replay_preset=pb2.ReplayPreset.CUSTOM,
    replay_id=saved_replay_id
)
```

### Flow Control

Control event processing rate:

```python
# Request multiple events at once for higher throughput
await client.subscribe_to_events(
    channel="/event/Print_Job__e",
    handler=handle_event,
    num_requested=10  # Process up to 10 events at a time
)
```

## Resources

- [Pub/Sub API Developer Guide](https://developer.salesforce.com/docs/platform/pub-sub-api/overview)
- [GitHub Repository](https://github.com/forcedotcom/pub-sub-api)
- [Python Quick Start](https://developer.salesforce.com/docs/platform/pub-sub-api/guide/qs-python-quick-start.html)

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review Salesforce Pub/Sub API documentation
3. Check server logs for detailed error messages
