# Single Integration User Authentication

## Overview

The Salesforce Printer Server uses a **single integration user** per Salesforce org for authentication. This is the recommended approach for server-to-server integrations.

## Why Single User Authentication?

Unlike user-facing applications, a printer server is a **background service** that:
- Doesn't need per-user authentication
- Operates on behalf of the organization, not individual users
- Should use a dedicated service account for security and auditing

## Authentication Methods (Best to Least)

### 1. ⭐ JWT Bearer Flow (RECOMMENDED)
**Best for: Production deployments**

```
┌─────────────────┐                    ┌──────────────────┐
│  Printer Server │──── JWT Token ────▶│   Salesforce     │
│                 │                    │   (validates     │
│  private_key.pem│                    │    certificate)  │
└─────────────────┘                    └──────────────────┘
        ▲                                       │
        │                                       │
        └──────── Access Token ─────────────────┘
```

**Characteristics:**
- ✅ Zero user interaction
- ✅ Most secure (certificate-based)
- ✅ Automatic token refresh
- ✅ Ideal for automated services
- ⚠️ Requires certificate setup

**When to use:**
- Production printer servers
- Automated/headless deployments
- High-security environments

### 2. Username-Password Flow
**Best for: Testing/Development**

```
┌─────────────────┐                    ┌──────────────────┐
│  Printer Server │── Username/Pass ──▶│   Salesforce     │
│                 │                    │                  │
│  (credentials   │                    │  (validates      │
│   in config)    │                    │   credentials)   │
└─────────────────┘                    └──────────────────┘
        ▲                                       │
        │                                       │
        └──────── Access Token ─────────────────┘
```

**Characteristics:**
- ✅ Simple setup
- ✅ No user interaction
- ⚠️ Requires security token
- ⚠️ Less secure (credentials in config)
- ⚠️ Affected by password changes

**When to use:**
- Development/testing environments
- Quick proof-of-concept
- When JWT setup is not possible

### 3. Web Server Flow (Interactive)
**Best for: Initial setup only**

```
┌─────────────────┐                    ┌──────────────────┐
│  Printer Server │◀─── Browser ──────▶│   Salesforce     │
│                 │     (one-time)     │   Login Page     │
│  (stores        │                    │                  │
│   refresh token)│                    │                  │
└─────────────────┘                    └──────────────────┘
        │                                       │
        └──────── Refresh Token ────────────────┘
                  (used for future auth)
```

**Characteristics:**
- ✅ Easy initial setup
- ✅ Stores refresh token for reuse
- ⚠️ Requires one-time user interaction
- ⚠️ Refresh token can be revoked

**When to use:**
- First-time setup wizard
- When you want to avoid managing certificates
- Personal/small deployments

## Integration User Setup

Regardless of authentication method, create a dedicated integration user:

1. **Go to Setup** → **Users** → **New User**
2. **User Details:**
   - Username: `printer.integration@yourcompany.com`
   - Email: Your admin email
   - Profile: Create custom profile or clone "API Only User"
   - Role: Optional (for record visibility)

3. **Permissions Needed:**
   ```
   ✓ API Enabled
   ✓ View All Data (or specific object permissions)
   ✓ Read: Print_Job__c
   ✓ Edit: Print_Job__c (for status updates)
   ✓ Read: Printer__c
   ✓ Read: ContentDocument
   ✓ Subscribe to Platform Events
   ```

4. **Security Settings:**
   - Set **Login IP Ranges** to restrict to printer server IPs
   - Enable **Session Settings** → **Lock sessions to IP**
   - Consider **Login Hours** if needed

## Configuration Examples

### JWT (Recommended)
```toml
[auth]
method = "jwt"
client_id = "3MVG9..."
username = "printer.integration@company.com"
private_key_file = "/etc/sf_printer_server/private_key.pem"

[salesforce]
instance_url = "https://login.salesforce.com"
```

### Password (Simple)
```toml
[auth]
method = "password"
client_id = "3MVG9..."
client_secret = "ABC123..."
username = "printer.integration@company.com"
password = "MyPassword123SecToken456"

[salesforce]
instance_url = "https://login.salesforce.com"
```

### Web (Interactive)
```toml
[auth]
method = "web"
client_id = "3MVG9..."
client_secret = "ABC123..."

[salesforce]
instance_url = "https://login.salesforce.com"
```

## Multi-Org Support

If you need to connect to multiple Salesforce orgs (e.g., Production + Sandbox):

```bash
# Configure production
sf-printer-server config --profile prod set-auth --method jwt ...

# Configure sandbox
sf-printer-server config --profile sandbox set-auth --method jwt ...

# Start with specific profile
sf-printer-server start --profile prod
```

Each profile uses the **same integration user approach** - just different users in different orgs.

## Security Best Practices

1. **Use JWT for Production** - Most secure, no credentials in config
2. **Dedicated User** - Never use a personal user account
3. **Minimal Permissions** - Only grant what's needed for printing
4. **IP Restrictions** - Limit login to printer server IPs
5. **Monitor Access** - Review login history regularly
6. **Rotate Credentials** - Update certificates/passwords periodically

## Troubleshooting

### "No client_id configured"
```bash
sf-printer-server config set-auth --method jwt --client-id YOUR_KEY ...
```

### "Invalid Grant"
- Integration user not pre-authorized in Connected App
- Check username matches exactly (case-sensitive)
- Verify instance URL (login.salesforce.com vs test.salesforce.com)

### "IP Restricted"
- Add server IP to user's **Login IP Ranges**
- Or enable "Relax IP restrictions" in Connected App

## Summary

✅ **One integration user per org**  
✅ **JWT Bearer Flow for production**  
✅ **No per-user authentication needed**  
✅ **Service account model**  
✅ **Automatic token refresh**  

This approach is standard for enterprise integrations and follows Salesforce best practices.
