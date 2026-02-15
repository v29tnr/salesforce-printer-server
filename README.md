# Salesforce Printer Server

A production-ready server for managing printers and print jobs using Salesforce Platform Events.

## Features
- 🔄 Real-time event listening via Salesforce Streaming API
- 🖨️ ZPL (Zebra Programming Language) support
- 🔐 JWT or OAuth authentication
- 🐋 Docker containerized deployment
- 📝 Simple TOML configuration
- 🚀 One-command installation

## Quick Install

**On your Linux server:**

```bash
git clone https://github.com/v29tnr/salesforce-printer-server.git
cd salesforce-printer-server
make install
```

The installer will:
- ✅ Install Docker (if needed)
- ✅ Generate SSL certificates
- ✅ Guide you through Salesforce setup
- ✅ Configure and start the service

**That's it!** 🎉

## Quick Commands

**One-line commands for everything:**

```bash
make install    # First-time setup
make update     # Pull latest code and rebuild
make start      # Start the service
make stop       # Stop the service
make restart    # Restart the service
make logs       # View live logs
make config     # Edit configuration
make status     # Check service status
```

## Traditional Commands (if make not available)

```bash
# Setup & Updates
chmod +x install.sh update.sh && ./install.sh  # Install
git pull && docker compose build --no-cache && docker compose up -d --force-recreate  # Update

# Service Management
docker compose logs -f         # View logs
docker compose down            # Stop service
docker compose restart         # Restart service
docker compose up -d           # Start
```

## Requirements
- Linux server (Ubuntu, Debian, CentOS, etc.)
- Docker (auto-installed if missing)
- Salesforce org with API access

## Documentation
- [Full Deployment Guide](DEPLOYMENT.md) - Detailed deployment options
- [Salesforce Setup](docs/SALESFORCE_SETUP.md) - Salesforce configuration
- [Authentication Guide](docs/AUTHENTICATION.md) - Auth setup details

## Configuration

Configuration is stored in `config/config.toml`:

```toml
[salesforce]
instance_url = "https://login.salesforce.com"

[auth]
method = "jwt"
client_id = "YOUR_CONSUMER_KEY"
username = "integration.user@company.com"
private_key_file = "/app/certs/private_key.pem"

[logging]
level = "INFO"
```

> **Note:** Printer configuration (name, IP address, ZPL content) is managed in Salesforce and passed via Platform Events.

## Support

Questions? Issues?
- 📖 Check the [docs](docs/) directory
- 🐛 [Open an issue](https://github.com/v29tnr/salesforce-printer-server/issues)

## License
MIT License - See [LICENSE](LICENSE) file