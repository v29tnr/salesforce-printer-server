# Migration to Pub/Sub API - Linux Server Instructions

## Quick Migration (5 minutes)

Your server is currently running with the old CometD Streaming API. Here's how to upgrade to the new Pub/Sub API:

### Step 1: Pull the Latest Code

```bash
cd /path/to/salesforce-printer-server
git pull
```

### Step 2: Rebuild and Restart

Use the existing `make` command you're already familiar with:

```bash
make update
```

That's it! The update command will:
- Pull the latest code
- Rebuild the Docker image with Pub/Sub API dependencies
- Generate gRPC stub files automatically
- Restart the service

### Step 3: Verify It's Working

Check the logs to see the new Pub/Sub API in action:

```bash
make logs
```

You should see messages like:
```
✓ Connected to Pub/Sub API
Listening for events...
```

## What Changed?

### ✅ Better Performance
- Switched from HTTP long-polling to gRPC/HTTP2 streaming
- More efficient binary message encoding (Avro)
- Faster event delivery

### ✅ Universal Authentication Support
- **BIG WIN**: Your JWT tokens now work directly!
- No more special "streaming_password" workaround needed
- All OAuth types are supported (JWT, Web OAuth, Username-Password)

### ✅ Improved Reliability
- Automatic keepalive messages
- Better error handling
- Client-controlled flow control

## Configuration

**No configuration changes needed!** Your existing `config/config.toml` works as-is.

The server automatically:
- Uses your existing authentication setup
- Connects to the same event channels
- Processes events the same way

## Troubleshooting

### Build Fails

If the Docker build fails, try:

```bash
# Clean rebuild
make clean
docker compose build --no-cache
make start
```

### Check Service Status

```bash
make status
```

### View Detailed Logs

```bash
make logs
```

### Authentication Issues

The Pub/Sub API uses the same authentication as before, but now **all token types work**:

1. **JWT Authentication** (what you probably use):
   - Works perfectly with Pub/Sub API ✅
   - No changes needed to your config

2. **Web OAuth** (browser-based):
   ```bash
   make auth
   ```

3. **Username-Password**:
   - Add to config if needed

## Rollback (if needed)

If you need to rollback to the old version:

```bash
git checkout <previous-commit>
make update
```

## Firewall Configuration

The Pub/Sub API uses a different endpoint. If you have a strict firewall, allow:

**Outbound connection to:**
- `api.pubsub.salesforce.com:7443` (gRPC endpoint)

**Previously used:** `<your-instance>.salesforce.com:443` (CometD endpoint)

Most firewalls allow HTTPS (443) and custom ports by default, but if you have issues, check your firewall rules.

## Need Help?

1. Check logs: `make logs`
2. Check status: `make status`
3. View full documentation: [`docs/PUBSUB_API.md`](docs/PUBSUB_API.md)
4. File an issue on GitHub

## Manual Setup (if not using Docker)

If you're running directly on the server without Docker:

```bash
# 1. Pull latest code
git pull

# 2. Install dependencies
pip install grpcio grpcio-tools avro-python3 certifi

# 3. Generate stub files
python scripts/generate_stubs.py

# 4. Restart service
# (however you normally restart - systemd, supervisor, etc.)
systemctl restart sf-printer-server  # or your command
```

## Verification Checklist

After migration, verify:

- [ ] Service is running: `make status`
- [ ] Logs show "Connected to Pub/Sub API": `make logs`
- [ ] Authentication successful (check logs)
- [ ] Events are being received (publish a test event)
- [ ] No error messages in logs

## Performance Comparison

You should notice:
- **Faster event delivery** (gRPC vs HTTP long-polling)
- **Lower CPU usage** (binary encoding vs JSON)
- **Better connection stability** (HTTP/2 multiplexing)

## Questions?

The migration is backward-compatible and should be seamless. Your existing configuration, authentication, and event channels all work exactly the same way.
