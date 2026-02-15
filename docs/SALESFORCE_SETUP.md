# Salesforce Setup Guide

This guide explains how to set up the required Salesforce components for the Printer Server.

## Two Setup Options

### Option 1: Automated Package Installation (Recommended) ⭐

We provide an **unmanaged package** that contains all custom objects and platform events. This is the easiest method.

```bash
# Generate the package
sf-printer-server salesforce generate-package

# This creates a `salesforce_package/` directory with:
#   - Custom objects (Printer__c, Print_Job__c)
#   - Platform event (Print_Job__e)
#   - package.xml manifest
```

**Deploy using Salesforce CLI:**

```bash
# Install Salesforce CLI if not already installed
# https://developer.salesforce.com/tools/sfdxcli

# Authenticate to your org
sfdx force:auth:web:login -a production

# Deploy the package
cd salesforce_package
sfdx force:source:deploy -p . -u production
```

**That's it!** All objects and events are now in your org.

---

### Option 2: Manual Setup

If you prefer manual setup or cannot use Salesforce CLI:

## Step 1: Create a Connected App in Salesforce
1. Log in to your Salesforce account.
2. Navigate to **Setup**.
3. In the Quick Find box, type **App Manager** and select it.
4. Click on **New Connected App**.
5. Fill in the required fields:
   - **Connected App Name**: Salesforce Printer Server
   - **API Name**: Salesforce_Printer_Server
   - **Contact Email**: [Your Email]
6. Under **API (Enable OAuth Settings)**:
   - Check **Enable OAuth Settings**.
   - Set the **Callback URL** to `http://localhost:5000/callback` (or your server's URL).
   - Select the required OAuth scopes, such as:
     - `Full access (full)`
     - `Perform requests on your behalf at any time (refresh_token, offline_access)`
7. Click **Save**.

## Step 2: Retrieve Consumer Key and Secret
1. After saving the connected app, you will be redirected to the app's detail page.
2. Note down the **Consumer Key** and **Consumer Secret**. You will need these for the printer server configuration.

## Step 3: Configure the Salesforce Printer Server
1. Install the Salesforce Printer Server using pip:
   ```
   pip install salesforce-printer-server
   ```
2. Run the installer to set up the configuration:
   ```
   sf_printer_server install
   ```
3. Follow the prompts to enter the **Consumer Key** and **Consumer Secret** obtained from the connected app.

## Step 4: Start the Printer Server
1. After configuration, start the printer server:
   ```
   sf_printer_server start
   ```
2. The server will begin listening for platform events related to print jobs.

## Step 5: Verify the Setup
- Check the server logs to ensure it is running without errors.
- Test the connection by sending a test print job through the Salesforce interface.

## Help and Support
For additional help, you can access the help menu by running:
```
sf_printer_server help
```

This will provide you with commands and options available for managing the printer server. 

## Conclusion
You have successfully set up the Salesforce Printer Server and connected it to your Salesforce environment. For further customization and usage, refer to the project documentation.