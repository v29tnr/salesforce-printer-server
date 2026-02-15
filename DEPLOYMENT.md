# Deployment Guide

## Prerequisites
- Linux server with Docker installed
- Access to Salesforce (to create Connected App)
- Network access to your printers

## Quick Deployment (Docker)

### 1. Clone the repository
```bash
git clone https://github.com/v29tnr/salesforce-printer-server.git
cd salesforce-printer-server
```

### 2. Add your user to docker group (if needed)
```bash
sudo usermod -aG docker $USER
newgrp docker
```

### 3. Run deployment script
```bash
chmod +x deploy.sh
./deploy.sh
```

### 4. Configure Salesforce credentials
```bash
nano config/config.toml
```

Update with your Salesforce settings:
```toml
[salesforce]
instance_url = "https://login.salesforce.com"  # or https://test.salesforce.com for sandbox

[auth]
method = "jwt"  # or "password" for testing
client_id = "YOUR_CONSUMER_KEY"
username = "your.integration.user@company.com"
private_key_file = "/app/certs/private_key.pem"

[printer]
default_printer = "Zebra_Printer_1"
zpl_enabled = true

[print_job]
max_retries = 3
retry_delay = 5
```

### 5. Set up JWT Authentication (Recommended)

#### Generate certificates locally
```bash
mkdir -p certs
cd certs

# Generate private key
openssl genrsa -out private_key.pem 2048

# Generate certificate (valid 2 years)
openssl req -new -x509 -key private_key.pem -out certificate.crt -days 730 \
  -subj "/C=US/ST=CA/L=SF/O=PrinterServer/CN=SF-Printer-Server"

cd ..
```

#### Create Connected App in Salesforce
1. Go to **Setup → App Manager → New Connected App**
2. Fill in:
   - **Connected App Name**: Printer Server
   - **API Name**: Printer_Server
   - **Contact Email**: your@email.com
3. **Enable OAuth Settings**:
   - ✓ Enable OAuth Settings
   - **Callback URL**: `https://login.salesforce.com`
   - **Selected OAuth Scopes**:
     - Access and manage your data (api)
     - Perform requests on your behalf at any time (refresh_token, offline_access)
4. **Scroll down to Flow Enablement**:
   - ✓ **Enable JWT Bearer Flow**
   - **Upload Certificate**: `certificate.crt` file from your `certs/` directory
5. Click **Save** and wait 2-10 minutes
6. After saving, click **Manage → Edit Policies**:
   - **Permitted Users**: Admin approved users are pre-authorized
   - Click **Save**
7. Click **Manage Profiles** or **Manage Permission Sets**:
   - Add your integration user's profile/permission set

#### Get Consumer Key
1. Go back to your Connected App
2. Click **View** or **Manage**
3. Copy the **Consumer Key** and paste it into `config/config.toml` as `client_id`

### 6. Start the server
```bash
docker-compose up -d
```

### 7. View logs
```bash
docker-compose logs -f
```

### 8. Verify it's running
```bash
docker ps
```

## Alternative: Manual Deployment (without Docker)

### 1. Install dependencies
```bash
sudo apt update
sudo apt install python3 python3-pip

cd salesforce-printer-server
pip3 install --user .
```

### 2. Run the installer
```bash
~/.local/bin/sf-printer-server install
# OR
python3 -m sf_printer_server.installer
```

### 3. Create systemd service
```bash
sudo nano /etc/systemd/system/sf-printer-server.service
```

Add:
```ini
[Unit]
Description=Salesforce Printer Server
After=network.target

[Service]
Type=simple
User=v29
WorkingDirectory=/home/v29/salesforce-printer-server
ExecStart=/home/v29/.local/bin/sf-printer-server start
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 4. Enable and start
```bash
sudo systemctl daemon-reload
sudo systemctl enable sf-printer-server
sudo systemctl start sf-printer-server
sudo systemctl status sf-printer-server
```

## Troubleshooting

### Check logs (Docker)
```bash
docker-compose logs -f sf-printer-server
```

### Check logs (systemd)
```bash
sudo journalctl -u sf-printer-server -f
```

### Restart service
```bash
# Docker
docker-compose restart

# Systemd
sudo systemctl restart sf-printer-server
```

### Update deployment
```bash
git pull
docker-compose down
docker-compose build
docker-compose up -d
```

## Security Notes

- Keep your `config.toml` and `private_key.pem` secure
- Use JWT authentication for production (not username/password)
- Restrict file permissions:
  ```bash
  chmod 600 config/config.toml
  chmod 600 certs/private_key.pem
  ```
- Consider using Docker secrets for sensitive data in production

## Support

For detailed documentation, see:
- [docs/AUTHENTICATION.md](docs/AUTHENTICATION.md) - Authentication setup
- [docs/SALESFORCE_SETUP.md](docs/SALESFORCE_SETUP.md) - Salesforce configuration
- [docs/AUTH_QUICKSTART.md](docs/AUTH_QUICKSTART.md) - Quick auth guide
