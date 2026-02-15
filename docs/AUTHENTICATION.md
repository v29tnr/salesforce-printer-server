# Authentication Guide

The Salesforce Printer Server supports multiple authentication methods. For production deployments, we **strongly recommend JWT Bearer Flow** as it provides secure, automated authentication without requiring user interaction.

## Recommended: JWT Bearer Flow (Server-to-Server)

This is the **best method for production printer servers** because:
- ✅ No user interaction required
- ✅ Works with a single integration user per org
- ✅ Most secure - uses certificate-based authentication
- ✅ Tokens refresh automatically
- ✅ Perfect for headless/service deployments

### Setup Steps

#### 1. Create Integration User in Salesforce

1. Go to **Setup** → **Users** → **Users**
2. Click **New User**
3. Create a dedicated integration user (e.g., `printer.integration@yourcompany.com`)
4. Assign appropriate profile/permission set with access to:
   - Print Job custom objects
   - Printer custom objects
   - ContentDocument records
   - Platform Events

#### 2. Generate Certificate and Private Key

Run these commands on your printer server:

```bash
# Generate private key
openssl genrsa -out private_key.pem 2048

# Generate certificate signing request
openssl req -new -key private_key.pem -out cert.csr

# Generate self-signed certificate (valid for 2 years)
openssl x509 -req -days 730 -in cert.csr -signkey private_key.pem -out certificate.crt

# Store private key securely
sudo mkdir -p /etc/sf_printer_server
sudo mv private_key.pem /etc/sf_printer_server/
sudo chmod 600 /etc/sf_printer_server/private_key.pem
```

#### 3. Create Connected App in Salesforce

1. Go to **Setup** → **App Manager** → **New Connected App**
2. Fill in basic information:
   - **Connected App Name**: `Printer Server`
   - **API Name**: `Printer_Server`
   - **Contact Email**: Your email
3. Enable OAuth Settings:
   - ✅ **Enable OAuth Settings**
   - **Callback URL**: `https://login.salesforce.com` (not used for JWT but required)
   - **Use digital signatures**: ✅ Check this
   - Upload your `certificate.crt` file
   - **Selected OAuth Scopes**:
     - Access and manage your data (api)
     - Perform requests on your behalf at any time (refresh_token, offline_access)
4. Click **Save**
5. Click **Manage Consumer Details** to get your **Consumer Key** (Client ID)

#### 4. Pre-Authorize the Integration User

1. Go to **Setup** → **App Manager**
2. Find your Connected App → **Manage**
3. Click **Edit Policies**
4. **Permitted Users**: Select "Admin approved users are pre-authorized"
5. Click **Save**
6. Click **Manage Profiles** or **Manage Permission Sets**
7. Add the profile/permission set of your integration user

#### 5. Configure Printer Server

Run the configuration command:

```bash
sf-printer-server config set-auth \
  --method jwt \
  --client-id "YOUR_CONSUMER_KEY" \
  --username "printer.integration@yourcompany.com" \
  --private-key "/etc/sf_printer_server/private_key.pem" \
  --instance-url "https://login.salesforce.com"
```

Or manually edit `~/.sf_printer_server/config.toml`:

```toml
[salesforce]
instance_url = "https://login.salesforce.com"
api_version = "60.0"

[auth]
method = "jwt"
client_id = "YOUR_CONSUMER_KEY_HERE"
username = "printer.integration@yourcompany.com"
private_key_file = "/etc/sf_printer_server/private_key.pem"
```

#### 6. Test Authentication

```bash
sf-printer-server auth test
```

That's it! The server will automatically authenticate using JWT whenever it starts.

---

## Alternative: Username-Password Flow (Simple but Less Secure)

Use this for **testing only** or if JWT setup is not possible.

### Setup Steps

1. Create integration user in Salesforce (same as above)
2. Get the user's **Security Token**:
   - Login as the integration user
   - Go to **Settings** → **Reset My Security Token**
   - Token will be emailed
3. Enable Username-Password flow in Connected App:
   - **Setup** → **App Manager** → Your Connected App → **Manage**
   - **Edit Policies**
   - **Permitted Users**: Admin approved users are pre-authorized
   - **IP Relaxation**: Relax IP restrictions (or add your server IP to the user's profile)
4. Configure:

```bash
sf-printer-server config set-auth \
  --method password \
  --client-id "YOUR_CONSUMER_KEY" \
  --client-secret "YOUR_CONSUMER_SECRET" \
  --username "printer.integration@yourcompany.com" \
  --password "password+securitytoken"
```

**Note**: The password must include the security token appended (e.g., if password is `MyPass123` and token is `AbC123`, use `MyPass123AbC123`)

---

## Alternative: Web Server Flow (One-Time Setup)

Use this only for **initial setup** if you want to use a refresh token approach.

### Setup Steps

1. Create Connected App with:
   - **Callback URL**: `http://localhost:8888/oauth/callback`
   - **OAuth Scopes**: api, refresh_token
2. Run initial authentication:

```bash
sf-printer-server auth login
```

This will:
- Open your browser
- Prompt you to login to Salesforce
- Automatically capture the OAuth callback
- Store a refresh token for future use

After initial setup, the server will use the refresh token automatically.

---

## Security Best Practices

### For JWT Flow (Recommended)
- ✅ Store private key in secure location (`/etc/sf_printer_server/`)
- ✅ Set restrictive file permissions (`chmod 600`)
- ✅ Use a dedicated integration user (not an admin)
- ✅ Rotate certificates every 1-2 years
- ✅ Monitor integration user login history

### For All Methods
- ✅ Create a dedicated integration user per environment (Dev, Sandbox, Production)
- ✅ Use minimal permissions (only what's needed for printing)
- ✅ Enable **Login IP Ranges** on the user's profile to restrict access
- ✅ Monitor failed authentication attempts
- ✅ Regularly review Connected App OAuth usage

---

## Troubleshooting

### "Invalid Grant" Error
- Ensure integration user is pre-authorized in Connected App
- Check that username matches exactly (case-sensitive)
- Verify instance URL is correct (`login.salesforce.com` for production, `test.salesforce.com` for sandboxes)

### Certificate Errors
- Verify certificate was uploaded to Connected App correctly
- Ensure private key matches the certificate
- Check that private key file path is correct and readable

### Token Expired
- Tokens should refresh automatically
- If refresh fails, re-run authentication
- Check that integration user account is active

### "IP Restricted" Error
- Add server IP to integration user's profile **Login IP Ranges**
- Or enable "Relax IP restrictions" in Connected App policies

---

## Multi-Org Setup

If you need to connect to **multiple Salesforce orgs** (e.g., Production + Sandbox):

1. Create separate integration users in each org
2. Create separate Connected Apps or use the same Consumer Key (if using JWT)
3. Configure multiple profiles:

```bash
# Production
sf-printer-server config --profile production set-auth --method jwt ...

# Sandbox
sf-printer-server config --profile sandbox set-auth --method jwt ...

# Run with specific profile
sf-printer-server start --profile production
```

---

## Summary

| Method | Best For | User Interaction | Security | Setup Complexity |
|--------|----------|------------------|----------|------------------|
| **JWT Bearer** ⭐ | Production servers | None | Highest | Medium |
| Username-Password | Testing/Development | None | Medium | Low |
| Web Server Flow | Initial setup | One-time | Medium | Low |

**Recommendation**: Use **JWT Bearer Flow** for all production deployments.
