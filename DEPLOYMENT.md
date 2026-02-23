# Deployment Guide

## Prerequisites
- Linux server with Docker installed
- Salesforce org access to create a Connected App
- Network access to your printers

---

## Quick Install (Recommended)

```bash
git clone https://github.com/v29tnr/salesforce-printer-server.git
cd salesforce-printer-server
chmod +x install.sh
./install.sh
```

The installer will walk you through every step interactively.

---

## Step 1 — Create a Salesforce Connected App

> **No certificates, no username/password required.**  
> Authentication uses **OAuth 2.0 Client Credentials Flow** (Consumer Key + Secret only).

1. **Setup → App Manager → New Connected App**

2. **Basic Info**
   - Connected App Name: `Printer Server`
   - API Name: `Printer_Server`
   - Contact Email: *(your email)*

3. **Enable OAuth Settings**
   - ✓ Enable OAuth Settings
   - Callback URL: `https://localhost:8888/oauth/callback`  
     *(value doesn't matter for client credentials)*
   - Selected OAuth Scopes:
     - **Full access** (`full`)
     - **Access the identity URL service** (`api`)

4. **Flow Enablement** *(scroll down)*
   - ✓ Enable Authorization Code and Credentials Flow
   - ✓ Enable Client Credentials Flow

5. **OAuth Policies**
   - ✓ Require Secret for Web Server Flow
   - ✓ Require Proof Key for Code Exchange (PKCE)

6. Click **Save** — wait 2–10 minutes for changes to propagate.

7. Go back to the Connected App → **Manage Consumer Details**  
   Copy your **Consumer Key** and **Consumer Secret**.

---

## Step 2 — Configure the Server

The installer writes `config/config.toml` automatically. To edit it manually:

```bash
nano config/config.toml
```

```toml
# Salesforce Printer Server Configuration

[salesforce]
instance_url = "https://login.salesforce.com"   # or https://test.salesforce.com

[auth]
method        = "client_credentials"
client_id     = "YOUR_CONSUMER_KEY"
client_secret = "YOUR_CONSUMER_SECRET"

[logging]
level = "INFO"
```

After editing, restart the container:
```bash
docker compose restart
```

---

## Docker Commands

| Action | Command |
|--------|---------|
| View logs | `docker compose logs -f` |
| Stop | `docker compose down` |
| Restart | `docker compose restart` |
| Rebuild (after code changes) | `docker compose build --no-cache && docker compose up -d` |
| Status | `docker compose ps` |

---

## Full Wipe & Reinstall

```bash
# Stop and remove container + image
docker compose down --rmi all

# Remove the folder completely
cd ~
rm -rf salesforce-printer-server

# Fresh install
git clone https://github.com/v29tnr/salesforce-printer-server.git
cd salesforce-printer-server
chmod +x install.sh
./install.sh
```

---

## Troubleshooting

### Logs
```bash
docker compose logs -f sf-printer-server
```

### Auth errors (401 / invalid_client)
- Double-check Consumer Key and Secret in `config/config.toml`
- Ensure **Client Credentials Flow** is enabled on the Connected App
- Wait the full 2–10 minutes after saving the Connected App in Salesforce

### Container won't start
```bash
docker compose logs   # read the error
docker compose down
docker compose build --no-cache
docker compose up -d
```

---

## Security Notes

- `config/config.toml` contains your Consumer Secret — keep it out of source control
- File is created with `chmod 600` by the installer
- Consider using Docker secrets or environment variables for the secret in high-security environments
