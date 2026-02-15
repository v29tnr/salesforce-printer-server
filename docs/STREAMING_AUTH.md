# Streaming API Authentication

## Problem
JWT Bearer Flow tokens don't work with Salesforce Streaming API (CometD). This is a known Salesforce limitation.

## Solutions

### Option 1: Browser-Based Authentication (Recommended - Easiest!)

Run the authentication setup script, which opens your browser:

```bash
make auth
# OR
./auth-setup.sh
```

**What happens:**
1. Opens your browser to Salesforce login
2. You log in normally
3. Token is saved and works with Streaming API
4. **No security token needed!**

**Connected App Requirements:**
- Callback URL: `http://localhost:8888/oauth/callback`
- OAuth Scopes: `Full access (full)`
- IP Relaxation: `Relax IP restrictions`

### Option 2: Username-Password OAuth (Manual)

If browser-based auth doesn't work (e.g., headless server), use password + security token:

1. **Get your security token:**
   - Setup → My Personal Information → Reset My Security Token
   - New token will be emailed to you

2. **Add to config:**
   ```toml
   [auth]
   streaming_password = "YourPasswordYourSecurityToken"
   ```
   Example: Password `MyPass123` + Token `abc456xyz` = `MyPass123abc456xyz`

3. **Restart:**
   ```bash
   make restart
   ```

## How It Works

The server uses **dual authentication**:
- **JWT Bearer Flow** for REST API operations (secure, no password)
- **Web/Password OAuth** for Streaming API (required by CometD)

Priority order:
1. ✅ Web OAuth token (from `make auth`)
2. ✅ Username-Password OAuth (from `streaming_password` config)
3. ❌ JWT token (doesn't work with Streaming API)

## Troubleshooting

**Error: `401::Authentication invalid` on CometD handshake**
- Run `make auth` to get a proper Streaming API token
- OR add `streaming_password` to config

**Browser auth fails:**
- Check Connected App has callback URL: `http://localhost:8888/oauth/callback`
- Ensure OAuth scope includes `Full access (full)`
- Verify IP Relaxation is enabled

**Token expires:**
- Web OAuth tokens have refresh tokens (automatic renewal)
- Run `make auth` again to get a new token

## References

- [Salesforce OAuth 2.0 Documentation](https://help.salesforce.com/s/articleView?id=sf.remoteaccess_authenticate.htm)
- [Streaming API Authentication](https://developer.salesforce.com/docs/atlas.en-us.api_streaming.meta/api_streaming/code_sample_auth_oauth.htm)
- [Why JWT Doesn't Work with CometD](https://developer.salesforce.com/docs/atlas.en-us.api_streaming.meta/api_streaming/using_streaming_api_stateless.htm)
