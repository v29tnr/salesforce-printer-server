# Automated Setup: What the Server Handles

## Overview

The Salesforce Printer Server installation process **automates as much as possible** to minimize manual configuration. Here's what happens automatically vs. what requires manual steps.

---

## ✅ Fully Automated by the Server

### 1. **SSL Certificate Generation**
```bash
sf-printer-server install
```

**What it does automatically:**
- ✅ Generates RSA 2048-bit private key
- ✅ Creates certificate signing request (CSR)
- ✅ Creates self-signed certificate (2-year validity)
- ✅ Stores in secure location (`~/.sf_printer_server/certs/`)
- ✅ Sets proper file permissions (600 for private key)
- ✅ Provides certificate file for Connected App upload

**You don't need to:**
- ❌ Manually run OpenSSL commands
- ❌ Understand certificate generation
- ❌ Worry about file permissions

---

### 2. **Configuration Management**
```bash
sf-printer-server config set-auth --method jwt ...
```

**What it does automatically:**
- ✅ Creates config directory structure
- ✅ Generates config.toml with proper format
- ✅ Validates configuration values
- ✅ Secures sensitive data
- ✅ Provides config templates

**You don't need to:**
- ❌ Manually edit TOML files
- ❌ Remember config file structure
- ❌ Look up correct paths

---

### 3. **Authentication Flow**
```bash
sf-printer-server start
```

**What it does automatically:**
- ✅ Loads configuration
- ✅ Authenticates via JWT
- ✅ Refreshes access tokens automatically
- ✅ Handles token expiration
- ✅ Retries on failure

**You don't need to:**
- ❌ Manually manage OAuth tokens
- ❌ Remember to refresh tokens
- ❌ Handle authentication errors

---

### 4. **Salesforce Package Generation**
```bash
sf-printer-server salesforce generate-package
```

**What it does automatically:**
- ✅ Creates complete Salesforce package structure
- ✅ Generates custom object metadata (Printer__c, Print_Job__c)
- ✅ Generates platform event metadata (Print_Job__e)
- ✅ Creates package.xml manifest
- ✅ Includes deployment instructions
- ✅ Proper XML formatting and API version

**You don't need to:**
- ❌ Write XML metadata manually
- ❌ Understand Salesforce metadata API
- ❌ Remember all required fields

---

### 5. **Interactive Setup Wizard**
```bash
sf-printer-server install
```

**What it does automatically:**
- ✅ Detects if already configured
- ✅ Guides through step-by-step setup
- ✅ Validates inputs
- ✅ Tests authentication after setup
- ✅ Provides clear instructions for each step
- ✅ Offers multiple setup methods (JWT/Password/Web)

**You don't need to:**
- ❌ Read extensive documentation first
- ❌ Figure out the correct order of steps
- ❌ Debug configuration issues

---

## ⚠️ Requires Manual Steps (One-Time)

### 1. **Connected App Creation in Salesforce**

**Why manual?**
- Salesforce requires admin credentials to create Connected Apps
- Security best practice: Don't give deployment tools admin access
- Simple UI-based process (5 minutes)

**What you do:**
1. Login to Salesforce Setup
2. App Manager → New Connected App
3. Upload certificate (provided by installer)
4. Copy Consumer Key
5. Pre-authorize integration user

**The installer helps by:**
- ✅ Displaying step-by-step instructions
- ✅ Pausing for you to complete each step
- ✅ Providing the certificate file path
- ✅ Showing exactly what values to enter

---

### 2. **Integration User Creation**

**Why manual?**
- Requires Salesforce admin access
- Organization-specific permission requirements
- User management is org-specific

**What you do:**
1. Setup → Users → New User
2. Create user: `printer.integration@company.com`
3. Assign appropriate profile/permissions

**The installer helps by:**
- ✅ Listing exact permissions needed
- ✅ Suggesting profile to use
- ✅ Explaining why each permission is needed

---

### 3. **Package Deployment to Salesforce**

**Why manual?**
- Requires Salesforce authentication
- Organization may have deployment policies
- Can use either UI or CLI

**What you do:**
```bash
# Option 1: Salesforce CLI (recommended)
sfdx force:auth:web:login -a myorg
sfdx force:source:deploy -p salesforce_package -u myorg

# Option 2: Manual through UI
# - Import custom objects manually
```

**The installer helps by:**
- ✅ Generates complete deployable package
- ✅ Provides deployment commands
- ✅ Includes README with instructions
- ✅ Validates metadata syntax

---

## 🤔 Could We Automate More?

### Technically Possible but Not Recommended:

#### ❌ Automated Connected App Creation
**Why not?**
- Requires admin username/password
- Security risk (storing admin credentials)
- Against Salesforce best practices
- Metadata API deployment is complex

**Alternative:**
- ✅ Interactive installer guides through manual creation (5 minutes)
- ✅ Could provide a Salesforce package to install

#### ❌ Automated User Creation
**Why not?**
- Requires admin access
- Organization-specific permission requirements
- License/profile management varies by org

**Alternative:**
- ✅ Installer provides exact instructions
- ✅ Lists specific permissions needed

#### ❌ Automated Package Deployment
**Why not?**
- Requires Salesforce authentication
- May require org approval process
- Deployment errors need human review

**Alternative:**
- ✅ Generate ready-to-deploy package
- ✅ Provide CLI commands
- ✅ Support both automated (CLI) and manual deployment

---

## 📦 Future Enhancement: Managed Package

### Possible Future Feature:

```bash
# Install from AppExchange (hypothetical)
sf-printer-server salesforce install-package
```

**This would:**
1. Open browser to AppExchange
2. Install pre-built managed package
3. Automatically creates objects and events
4. Still requires Connected App + integration user setup

**Benefits:**
- ✅ One-click installation of Salesforce components
- ✅ Automatic updates
- ✅ Pre-tested metadata

**Limitations:**
- ⚠️ Still need Connected App (security requirement)
- ⚠️ Still need integration user
- ⚠️ Requires AppExchange listing

---

## Summary: Automation Level

| Component | Automation | Method |
|-----------|------------|--------|
| Certificate generation | **100% Automated** | `sf-printer-server install` |
| Configuration | **100% Automated** | Interactive wizard |
| Package generation | **100% Automated** | `generate-package` command |
| Authentication | **100% Automated** | Auto-refresh tokens |
| Connected App | **Guided Manual** | Step-by-step instructions |
| Integration User | **Guided Manual** | Detailed permissions list |
| Package deployment | **Semi-Automated** | CLI commands provided |

---

## Recommended Installation Flow

### First-Time Setup (15 minutes total):

```bash
# 1. Install package (1 minute)
pip install sf-printer-server

# 2. Run installer (5 minutes)
sf-printer-server install
# - Generates certificate automatically
# - Guides through Connected App creation
# - Tests authentication

# 3. Deploy to Salesforce (5 minutes)
sf-printer-server salesforce generate-package
cd salesforce_package
sfdx force:auth:web:login -a myorg
sfdx force:source:deploy -p . -u myorg

# 4. Start server (instant)
sf-printer-server start
```

**Manual steps:**
- Creating Connected App (5 minutes, one-time)
- Creating integration user (3 minutes, one-time)

**Total effort:** ~15 minutes first time, then fully automated thereafter

---

## The Bottom Line

✅ **The server automates everything it safely can**
✅ **Manual steps are minimal and guided**
✅ **Security is prioritized over convenience**
✅ **One-time setup, then fully automated**

The installer strikes the right balance between automation and security best practices!
