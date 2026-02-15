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
chmod +x install.sh
./install.sh
```

The installer will:
- ✅ Install Docker (if needed)
- ✅ Generate SSL certificates
- ✅ Guide you through Salesforce setup
- ✅ Configure and start the service

**That's it!** 🎉

## Management Commands

```bash
# View logs
docker compose logs -f

# Stop service
docker compose down

# Restart service
docker compose restart

# Update to latest version
./update.sh

# Uninstall
./uninstall.sh
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

[printer]
default_printer = "Zebra_Printer"
zpl_enabled = true
```

## Support

Questions? Issues?
- 📖 Check the [docs](docs/) directory
- 🐛 [Open an issue](https://github.com/v29tnr/salesforce-printer-server/issues)

## License
MIT License - See [LICENSE](LICENSE) file