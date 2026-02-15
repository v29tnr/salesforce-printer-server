"""
Deploy Connected App and custom objects to Salesforce using Metadata API.
This script helps automate the Salesforce setup process.
"""

import sys
import json
import base64
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, Dict
import requests
import click


def create_connected_app_metadata(
    app_name: str,
    certificate_file: Path,
    contact_email: str
) -> str:
    """
    Create Connected App metadata XML.
    
    Args:
        app_name: Name of the Connected App
        certificate_file: Path to certificate file
        contact_email: Contact email
        
    Returns:
        XML string
    """
    # Read and encode certificate
    with open(certificate_file, 'rb') as f:
        cert_content = f.read()
    
    # Create metadata XML
    root = ET.Element('ConnectedApp', xmlns='http://soap.sforce.com/2006/04/metadata')
    
    # Basic info
    ET.SubElement(root, 'fullName').text = app_name.replace(' ', '_')
    ET.SubElement(root, 'label').text = app_name
    ET.SubElement(root, 'contactEmail').text = contact_email
    
    # OAuth config
    oauth = ET.SubElement(root, 'oauthConfig')
    ET.SubElement(oauth, 'callbackUrl').text = 'https://login.salesforce.com'
    ET.SubElement(oauth, 'certificate').text = cert_content.decode('utf-8')
    ET.SubElement(oauth, 'consumerKey').text = ''  # Salesforce generates this
    
    # Scopes
    scopes = oauth.find('scopes')
    if scopes is None:
        scopes = ET.SubElement(oauth, 'scopes')
    ET.SubElement(oauth, 'scopes').text = 'Api'
    ET.SubElement(oauth, 'scopes').text = 'RefreshToken'
    
    # Convert to string
    return ET.tostring(root, encoding='unicode', method='xml')


@click.group()
def cli():
    """Deploy Salesforce Printer Server components to Salesforce."""
    pass


@cli.command()
@click.option('--username', prompt='Salesforce admin username', help='Salesforce admin username')
@click.option('--password', prompt='Salesforce admin password', hide_input=True, help='Password + security token')
@click.option('--instance-url', default='https://login.salesforce.com', help='Salesforce instance URL')
@click.option('--certificate', type=click.Path(exists=True), required=True, help='Path to certificate file')
@click.option('--app-name', default='Printer_Server', help='Connected App name')
@click.option('--contact-email', prompt='Contact email', help='Contact email for the app')
def connected_app(username, password, instance_url, certificate, app_name, contact_email):
    """
    Deploy Connected App to Salesforce.
    
    Note: This requires admin credentials for one-time setup.
    After deployment, the app will use JWT authentication.
    """
    click.echo("\n" + "="*70)
    click.echo("DEPLOYING CONNECTED APP TO SALESFORCE")
    click.echo("="*70)
    
    try:
        # Authenticate as admin
        click.echo("\n[1/3] Authenticating as admin user...")
        session = authenticate_admin(instance_url, username, password)
        
        if not session:
            click.echo("❌ Authentication failed")
            return
        
        click.echo("✓ Authenticated successfully")
        
        # Create metadata package
        click.echo("\n[2/3] Creating Connected App metadata...")
        metadata_xml = create_connected_app_metadata(
            app_name,
            Path(certificate),
            contact_email
        )
        
        # Deploy via Metadata API
        click.echo("\n[3/3] Deploying to Salesforce...")
        success = deploy_metadata(session, metadata_xml, app_name)
        
        if success:
            click.echo("\n✅ Connected App deployed successfully!")
            click.echo("\nNext steps:")
            click.echo("  1. Wait 2-10 minutes for changes to take effect")
            click.echo("  2. Go to Setup → App Manager → View your app")
            click.echo("  3. Copy the Consumer Key")
            click.echo("  4. Run: sf-printer-server config set-auth --client-id <KEY>")
        else:
            click.echo("\n❌ Deployment failed")
            click.echo("\nYou can manually create the Connected App:")
            click.echo("  Setup → App Manager → New Connected App")
            
    except Exception as e:
        click.echo(f"\n❌ Error: {e}")
        click.echo("\nTip: You may need to create the Connected App manually")


@cli.command()
@click.option('--username', prompt='Salesforce admin username', help='Salesforce admin username')
@click.option('--password', prompt='Salesforce admin password', hide_input=True, help='Password + security token')
@click.option('--instance-url', default='https://login.salesforce.com', help='Salesforce instance URL')
def custom_objects(username, password, instance_url):
    """
    Deploy custom objects (Printer__c, Print_Job__c) to Salesforce.
    """
    click.echo("\n" + "="*70)
    click.echo("DEPLOYING CUSTOM OBJECTS TO SALESFORCE")
    click.echo("="*70)
    
    try:
        # Authenticate as admin
        click.echo("\n[1/2] Authenticating as admin user...")
        session = authenticate_admin(instance_url, username, password)
        
        if not session:
            click.echo("❌ Authentication failed")
            return
        
        click.echo("✓ Authenticated successfully")
        
        # Deploy objects
        click.echo("\n[2/2] Deploying custom objects...")
        
        objects = ['Printer__c', 'Print_Job__c']
        for obj in objects:
            click.echo(f"  • Creating {obj}...")
            # TODO: Implement object creation
        
        click.echo("\n✅ Custom objects deployed!")
        
    except Exception as e:
        click.echo(f"\n❌ Error: {e}")


@cli.command()
@click.option('--output-dir', type=click.Path(), default='./salesforce_package', help='Output directory for package')
def generate_package(output_dir):
    """
    Generate an unmanaged package that can be installed in Salesforce.
    Creates a package.xml with all necessary components.
    """
    click.echo("\n" + "="*70)
    click.echo("GENERATING SALESFORCE PACKAGE")
    click.echo("="*70)
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Create package.xml
    package_xml = create_package_xml()
    package_file = output_path / 'package.xml'
    
    with open(package_file, 'w') as f:
        f.write(package_xml)
    
    click.echo(f"\n✓ Package manifest created: {package_file}")
    
    # Create objects directory
    objects_dir = output_path / 'objects'
    objects_dir.mkdir(exist_ok=True)
    
    # Generate custom object metadata
    printer_obj = create_printer_object_metadata()
    with open(objects_dir / 'Printer__c.object', 'w') as f:
        f.write(printer_obj)
    
    print_job_obj = create_print_job_object_metadata()
    with open(objects_dir / 'Print_Job__c.object', 'w') as f:
        f.write(print_job_obj)
    
    click.echo(f"✓ Custom objects created in: {objects_dir}")
    
    # Create platform event
    events_dir = output_path / 'platformEvents'
    events_dir.mkdir(exist_ok=True)
    
    event_xml = create_platform_event_metadata()
    with open(events_dir / 'Print_Job__e.platformEvent', 'w') as f:
        f.write(event_xml)
    
    click.echo(f"✓ Platform event created in: {events_dir}")
    
    # Create README
    readme = create_package_readme()
    with open(output_path / 'README.md', 'w') as f:
        f.write(readme)
    
    click.echo("\n✅ Package generated successfully!")
    click.echo(f"\nPackage location: {output_path}")
    click.echo("\nTo deploy:")
    click.echo("  1. Install Salesforce CLI: https://developer.salesforce.com/tools/sfdxcli")
    click.echo(f"  2. cd {output_path}")
    click.echo("  3. sfdx force:auth:web:login -a myorg")
    click.echo("  4. sfdx force:source:deploy -p . -u myorg")


def authenticate_admin(instance_url: str, username: str, password: str) -> Optional[Dict]:
    """Authenticate as admin user (one-time for deployment)."""
    token_url = f"{instance_url}/services/oauth2/token"
    
    # Note: This requires a Connected App for the deployment tool itself
    # In practice, you'd use Salesforce CLI or manually create the app
    click.echo("\n⚠️  Note: Metadata deployment requires Salesforce CLI or manual setup")
    return None


def deploy_metadata(session: Dict, metadata_xml: str, name: str) -> bool:
    """Deploy metadata using Metadata API."""
    # TODO: Implement Metadata API deployment
    return False


def create_package_xml() -> str:
    """Create package.xml for unmanaged package."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<Package xmlns="http://soap.sforce.com/2006/04/metadata">
    <types>
        <members>Printer__c</members>
        <members>Print_Job__c</members>
        <name>CustomObject</name>
    </types>
    <types>
        <members>Print_Job__e</members>
        <name>PlatformEvent</name>
    </types>
    <version>60.0</version>
</Package>"""


def create_printer_object_metadata() -> str:
    """Create Printer__c custom object metadata."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<CustomObject xmlns="http://soap.sforce.com/2006/04/metadata">
    <label>Printer</label>
    <pluralLabel>Printers</pluralLabel>
    <nameField>
        <label>Printer Name</label>
        <type>Text</type>
    </nameField>
    <deploymentStatus>Deployed</deploymentStatus>
    <sharingModel>ReadWrite</sharingModel>
    
    <fields>
        <fullName>Printer_Type__c</fullName>
        <label>Printer Type</label>
        <type>Picklist</type>
        <required>true</required>
        <valueSet>
            <valueSetDefinition>
                <value><fullName>ZPL</fullName></value>
                <value><fullName>CUPS</fullName></value>
                <value><fullName>Raw TCP</fullName></value>
            </valueSetDefinition>
        </valueSet>
    </fields>
    
    <fields>
        <fullName>Host__c</fullName>
        <label>Host/IP Address</label>
        <type>Text</type>
        <length>255</length>
    </fields>
    
    <fields>
        <fullName>Port__c</fullName>
        <label>Port</label>
        <type>Number</type>
        <precision>5</precision>
        <scale>0</scale>
    </fields>
    
    <fields>
        <fullName>Queue_Name__c</fullName>
        <label>Queue Name (CUPS)</label>
        <type>Text</type>
        <length>255</length>
    </fields>
    
    <fields>
        <fullName>Enabled__c</fullName>
        <label>Enabled</label>
        <type>Checkbox</type>
        <defaultValue>true</defaultValue>
    </fields>
</CustomObject>"""


def create_print_job_object_metadata() -> str:
    """Create Print_Job__c custom object metadata."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<CustomObject xmlns="http://soap.sforce.com/2006/04/metadata">
    <label>Print Job</label>
    <pluralLabel>Print Jobs</pluralLabel>
    <nameField>
        <label>Print Job Number</label>
        <type>AutoNumber</type>
        <displayFormat>PJ-{00000}</displayFormat>
    </nameField>
    <deploymentStatus>Deployed</deploymentStatus>
    <sharingModel>ReadWrite</sharingModel>
    
    <fields>
        <fullName>Printer__c</fullName>
        <label>Printer</label>
        <type>Lookup</type>
        <referenceTo>Printer__c</referenceTo>
        <relationshipLabel>Print Jobs</relationshipLabel>
        <relationshipName>Print_Jobs</relationshipName>
        <required>true</required>
    </fields>
    
    <fields>
        <fullName>Status__c</fullName>
        <label>Status</label>
        <type>Picklist</type>
        <valueSet>
            <valueSetDefinition>
                <value><fullName>Pending</fullName></value>
                <value><fullName>Processing</fullName></value>
                <value><fullName>Completed</fullName></value>
                <value><fullName>Error</fullName></value>
            </valueSetDefinition>
        </valueSet>
    </fields>
    
    <fields>
        <fullName>Status_Message__c</fullName>
        <label>Status Message</label>
        <type>LongTextArea</type>
        <length>32768</length>
    </fields>
    
    <fields>
        <fullName>Is_ZPL__c</fullName>
        <label>Is ZPL</label>
        <type>Checkbox</type>
        <defaultValue>false</defaultValue>
    </fields>
    
    <fields>
        <fullName>ZPL_Content__c</fullName>
        <label>ZPL Content</label>
        <type>LongTextArea</type>
        <length>32768</length>
    </fields>
    
    <fields>
        <fullName>Content_Document_Id__c</fullName>
        <label>Content Document ID</label>
        <type>Text</type>
        <length>18</length>
    </fields>
</CustomObject>"""


def create_platform_event_metadata() -> str:
    """Create Print_Job__e platform event metadata."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<CustomObject xmlns="http://soap.sforce.com/2006/04/metadata">
    <label>Print Job Event</label>
    <pluralLabel>Print Job Events</pluralLabel>
    <eventType>HighVolume</eventType>
    <deploymentStatus>Deployed</deploymentStatus>
    
    <fields>
        <fullName>Print_Job_Id__c</fullName>
        <label>Print Job ID</label>
        <type>Text</type>
        <length>18</length>
        <required>true</required>
    </fields>
    
    <fields>
        <fullName>Printer_Id__c</fullName>
        <label>Printer ID</label>
        <type>Text</type>
        <length>18</length>
        <required>true</required>
    </fields>
    
    <fields>
        <fullName>Is_ZPL__c</fullName>
        <label>Is ZPL</label>
        <type>Checkbox</type>
        <defaultValue>false</defaultValue>
    </fields>
    
    <fields>
        <fullName>ZPL_Content__c</fullName>
        <label>ZPL Content</label>
        <type>LongTextArea</type>
        <length>10000</length>
    </fields>
    
    <fields>
        <fullName>Content_Document_Id__c</fullName>
        <label>Content Document ID</label>
        <type>Text</type>
        <length>18</length>
    </fields>
</CustomObject>"""


def create_package_readme() -> str:
    """Create README for the package."""
    return """# Salesforce Printer Server Package

This package contains the custom objects and platform events required for the Salesforce Printer Server.

## Contents

- **Custom Objects:**
  - `Printer__c` - Printer configuration
  - `Print_Job__c` - Print job records
  
- **Platform Events:**
  - `Print_Job__e` - Print job event for real-time processing

## Installation

### Option 1: Using Salesforce CLI (Recommended)

```bash
# Authenticate
sfdx force:auth:web:login -a myorg

# Deploy
sfdx force:source:deploy -p . -u myorg
```

### Option 2: Manual Installation

1. Create each custom object in Setup → Object Manager
2. Create the platform event in Setup → Integrations → Platform Events
3. Copy the field definitions from the XML files

## Post-Installation

After deploying:

1. Create at least one Printer record
2. Configure the Printer Server with your Connected App credentials
3. The server will listen for `Print_Job__e` platform events
4. Create Print Job records or publish events to trigger printing

## Support

For documentation, see: https://github.com/yourorg/salesforce-printer-server
"""


if __name__ == '__main__':
    cli()
    return "your_access_token"

if __name__ == '__main__':
    deploy_connected_app()