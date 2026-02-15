# Quick Start: Authentication Setup

## TL;DR - Fastest Setup

### Option 1: JWT (Production - Recommended) ⭐

```bash
# 1. Generate certificate (on printer server)
openssl genrsa -out private_key.pem 2048
openssl req -new -key private_key.pem -out cert.csr
openssl x509 -req -days 730 -in cert.csr -signkey private_key.pem -out cert.crt

# 2. In Salesforce:
#    - Create integration user: printer.integration@company.com
#    - Create Connected App with digital signature (upload cert.crt)
#    - Pre-authorize the integration user
#    - Copy Consumer Key

# 3. Configure printer server
sf-printer-server config set-auth \
  --method jwt \
  --client-id "3MVG9..." \
  --username "printer.integration@company.com" \
  --private-key "private_key.pem"

# 4. Test
sf-printer-server auth test

# 5. Start server
sf-printer-server start
```

**Done!** Server will authenticate automatically every time it starts. No user interaction needed.

---

### Option 2: Password (Testing Only)

```bash
# 1. In Salesforce:
#    - Create integration user: printer.integration@company.com
#    - Get security token (Settings → Reset Security Token)
#    - Create Connected App (enable OAuth, get Consumer Key & Secret)
#    - Pre-authorize the integration user

# 2. Configure printer server
sf-printer-server config set-auth \
  --method password \
  --client-id "3MVG9..." \
  --client-secret "ABC123..." \
  --username "printer.integration@company.com" \
  --password "MyPassword123SecToken456"

# 3. Start server
sf-printer-server start
```

**Note:** Password must include security token appended to the end.

---

### Option 3: Web Login (One-Time Interactive)

```bash
# 1. In Salesforce:
#    - Create Connected App
#    - Callback URL: http://localhost:8888/oauth/callback
#    - Copy Consumer Key & Secret

# 2. Configure printer server
sf-printer-server config set-auth \
  --method web \
  --client-id "3MVG9..." \
  --client-secret "ABC123..."

# 3. Login (opens browser, one time only)
sf-printer-server auth login

# 4. Start server (uses stored refresh token)
sf-printer-server start
```

**Note:** After initial login, server will use refresh token automatically.

---

## Which Method Should I Use?

| Scenario | Use This Method |
|----------|----------------|
| 🏢 Production server | JWT ⭐ |
| 🧪 Development/Testing | Password |
| 💻 Personal/Desktop use | Web Login |
| 🔒 High security required | JWT ⭐ |
| ⚡ Quick proof-of-concept | Password |

---

## Common Issues

### "Invalid client_id" or "Invalid client credentials"
- Double-check Consumer Key/Secret copied correctly
- Verify Connected App is active in Salesforce

### "Invalid username or password"
- For password method: Did you append security token to password?
- Check username is exact (case-sensitive)
- Verify user is active in Salesforce

### "User hasn't approved this consumer"
- In Connected App settings, set "Permitted Users" to "Admin approved users are pre-authorized"
- Click "Manage Profiles" or "Manage Permission Sets"
- Add your integration user's profile/permission set

### "IP restricted or invalid login hours"
- Add server IP to user profile's "Login IP Ranges"
- Or enable "Relax IP restrictions" in Connected App policies

### Browser doesn't open for web login
- Copy the URL from terminal and open manually
- After login, copy the callback URL and paste when prompted

---

## Complete Setup Example (JWT)

### Step 1: Create Certificate
```bash
cd /tmp
openssl genrsa -out private_key.pem 2048
openssl req -new -key private_key.pem -out cert.csr \
  -subj "/C=US/ST=CA/L=SF/O=MyCompany/CN=PrinterServer"
openssl x509 -req -days 730 -in cert.csr -signkey private_key.pem -out cert.crt

# Secure the private key
sudo mkdir -p /etc/sf_printer_server
sudo mv private_key.pem /etc/sf_printer_server/
sudo chmod 600 /etc/sf_printer_server/private_key.pem
```

### Step 2: Salesforce Setup
1. **Create Integration User:**
   - Setup → Users → New User
   - Username: `printer.integration@yourcompany.com`
   - Profile: "API Only User" or custom profile with API access
   - Grant permissions for Print Job and Printer objects

2. **Create Connected App:**
   - Setup → App Manager → New Connected App
   - Name: "Printer Server"
   - Enable OAuth Settings ✓
   - Callback: `https://login.salesforce.com` (required but not used)
   - Use digital signatures ✓ → Upload `cert.crt`
   - Scopes: "Access and manage your data (api)", "Perform requests at any time (refresh_token)"
   - Save

3. **Pre-authorize User:**
   - App Manager → Find "Printer Server" → Manage
   - Edit Policies
   - Permitted Users: "Admin approved users are pre-authorized"
   - Save
   - Manage Profiles → Add integration user's profile

4. **Get Consumer Key:**
   - App Manager → Printer Server → View
   - Copy "Consumer Key"

### Step 3: Configure Server
```bash
sf-printer-server config set-auth \
  --method jwt \
  --client-id "3MVG9.A2ko_your_consumer_key_here" \
  --username "printer.integration@yourcompany.com" \
  --private-key "/etc/sf_printer_server/private_key.pem" \
  --instance-url "https://login.salesforce.com"
```

### Step 4: Test & Run
```bash
# Test authentication
sf-printer-server auth test

# Should output:
# ✓ Authentication successful
# ✓ Connected to: https://yourinstance.salesforce.com
# ✓ API Version: 60.0

# Start the server
sf-printer-server start
```

**That's it!** The server is now authenticated and will automatically refresh tokens as needed.

---

## Need Help?

- **Full Documentation:** See `docs/AUTHENTICATION.md`
- **Salesforce Setup:** See `docs/SALESFORCE_SETUP.md`
- **Test Auth:** `sf-printer-server auth test`
- **View Config:** `sf-printer-server config show`
- **Help:** `sf-printer-server --help`
