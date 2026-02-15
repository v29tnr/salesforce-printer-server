"""
Interactive installer for Salesforce Printer Server.
Handles initial setup including JWT certificate generation and Salesforce configuration.
"""

import os
import sys
import subprocess
import logging
from pathlib import Path
from typing import Optional, Dict, Any
import tempfile
import shutil

logger = logging.getLogger(__name__)


class PrinterServerInstaller:
    """Interactive installer for first-time setup."""
    
    def __init__(self):
        self.config_dir = Path.home() / '.sf_printer_server'
        self.cert_dir = self.config_dir / 'certs'
        self.config = {}
        
    def run(self):
        """Run the interactive installation process."""
        self._print_welcome()
        
        # Check if already configured
        if self._is_configured():
            print("\n⚠️  Configuration already exists!")
            response = input("Do you want to reconfigure? (yes/no): ").strip().lower()
            if response not in ['yes', 'y']:
                print("Installation cancelled.")
                return
        
        # Choose setup method
        print("\n" + "="*70)
        print("SETUP METHOD")
        print("="*70)
        print("\n1. Automatic Setup (Recommended) - Generate certificate and guide you")
        print("2. Manual Setup - I already have a certificate and Connected App")
        print("3. Quick Test Setup - Use username/password (testing only)")
        
        choice = input("\nChoose setup method (1-3): ").strip()
        
        if choice == '1':
            self._automatic_setup()
        elif choice == '2':
            self._manual_setup()
        elif choice == '3':
            self._test_setup()
        else:
            print("Invalid choice. Exiting.")
            return
        
        self._print_completion()
    
    def _print_welcome(self):
        """Print welcome banner."""
        print("\n" + "="*70)
        print(" " * 15 + "SALESFORCE PRINTER SERVER")
        print(" " * 20 + "Installation Wizard")
        print("="*70)
        print("\nThis wizard will help you set up JWT authentication with Salesforce.")
        print("You'll need:")
        print("  • Access to Salesforce Setup")
        print("  • Ability to create a Connected App")
        print("  • An integration user account")
    
    def _is_configured(self) -> bool:
        """Check if already configured."""
        config_file = self.config_dir / 'config.toml'
        return config_file.exists()
    
    def _automatic_setup(self):
        """Automatic setup with certificate generation."""
        print("\n" + "="*70)
        print("AUTOMATIC JWT SETUP")
        print("="*70)
        
        # Step 1: Generate certificate
        print("\n[Step 1/5] Generating SSL certificate...")
        cert_info = self._generate_certificate()
        if not cert_info:
            print("❌ Failed to generate certificate. Please check OpenSSL is installed.")
            return
        
        print(f"✓ Certificate generated at: {cert_info['cert_file']}")
        print(f"✓ Private key at: {cert_info['key_file']}")
        
        # Step 2: Get Salesforce instance info
        print("\n[Step 2/5] Salesforce Configuration")
        instance_type = self._prompt_instance_type()
        self.config['salesforce.instance_url'] = instance_type
        
        # Step 3: Integration user
        print("\n[Step 3/5] Integration User")
        print("\nYou need to create a dedicated integration user in Salesforce:")
        print("  1. Go to Setup → Users → New User")
        print("  2. Create user with username like: printer.integration@yourcompany.com")
        print("  3. Assign 'API Only User' profile or custom profile with API access")
        print("  4. Grant permissions for Print Job and Printer objects")
        
        username = input("\nEnter the integration user's username: ").strip()
        while not username or '@' not in username:
            print("Please enter a valid email address.")
            username = input("Enter the integration user's username: ").strip()
        
        self.config['auth.username'] = username
        
        # Step 4: Instructions for Connected App
        print("\n[Step 4/5] Create Connected App in Salesforce")
        print("\n" + "─"*70)
        self._print_connected_app_instructions(cert_info['cert_file'])
        print("─"*70)
        
        input("\nPress ENTER once you've created the Connected App...")
        
        # Step 5: Get Consumer Key
        print("\n[Step 5/5] Connected App Configuration")
        print("\nFrom your Connected App in Salesforce:")
        print("  1. Go to Setup → App Manager → Find your app → View")
        print("  2. Copy the 'Consumer Key'")
        
        client_id = input("\nPaste the Consumer Key here: ").strip()
        while not client_id:
            print("Consumer Key is required.")
            client_id = input("Paste the Consumer Key here: ").strip()
        
        self.config['auth.method'] = 'jwt'
        self.config['auth.client_id'] = client_id
        self.config['auth.private_key_file'] = str(cert_info['key_file'])
        
        # Save configuration
        self._save_config()
        
        print("\n✓ Configuration saved successfully!")
        
        # Test authentication
        print("\n[Testing] Attempting to authenticate...")
        if self._test_authentication():
            print("✓ Authentication successful!")
        else:
            print("⚠️  Authentication test failed. Please check your configuration.")
            print("   You can test again later with: sf-printer-server auth test")
    
    def _manual_setup(self):
        """Manual setup for existing certificate."""
        print("\n" + "="*70)
        print("MANUAL JWT SETUP")
        print("="*70)
        
        # Get instance URL
        instance_type = self._prompt_instance_type()
        self.config['salesforce.instance_url'] = instance_type
        
        # Get client ID
        client_id = input("\nEnter your Connected App Consumer Key: ").strip()
        self.config['auth.client_id'] = client_id
        
        # Get username
        username = input("Enter integration user username: ").strip()
        self.config['auth.username'] = username
        
        # Get private key path
        print("\nEnter the path to your private key file:")
        key_file = input("Private key path: ").strip()
        
        if not Path(key_file).exists():
            print(f"⚠️  Warning: File not found: {key_file}")
            print("   Make sure the path is correct before starting the server.")
        
        self.config['auth.method'] = 'jwt'
        self.config['auth.private_key_file'] = key_file
        
        self._save_config()
        print("\n✓ Configuration saved!")
    
    def _test_setup(self):
        """Quick test setup with username/password."""
        print("\n" + "="*70)
        print("TEST SETUP (Username/Password)")
        print("="*70)
        print("\n⚠️  WARNING: This method is for testing only!")
        print("   For production, use JWT authentication.")
        
        # Get instance URL
        instance_type = self._prompt_instance_type()
        self.config['salesforce.instance_url'] = instance_type
        
        # Get credentials
        client_id = input("\nConnected App Consumer Key: ").strip()
        client_secret = input("Connected App Consumer Secret: ").strip()
        username = input("Salesforce username: ").strip()
        password = input("Salesforce password: ").strip()
        
        print("\nNote: You need to append your Security Token to the password.")
        print("Get token from: Settings → Reset My Security Token")
        security_token = input("Security Token: ").strip()
        
        full_password = password + security_token
        
        self.config['auth.method'] = 'password'
        self.config['auth.client_id'] = client_id
        self.config['auth.client_secret'] = client_secret
        self.config['auth.username'] = username
        self.config['auth.password'] = full_password
        
        self._save_config()
        print("\n✓ Configuration saved!")
    
    def _generate_certificate(self) -> Optional[Dict[str, Path]]:
        """Generate SSL certificate and private key."""
        try:
            # Create cert directory
            self.cert_dir.mkdir(parents=True, exist_ok=True)
            
            key_file = self.cert_dir / 'private_key.pem'
            csr_file = self.cert_dir / 'cert.csr'
            cert_file = self.cert_dir / 'certificate.crt'
            
            # Generate private key
            subprocess.run(
                ['openssl', 'genrsa', '-out', str(key_file), '2048'],
                check=True,
                capture_output=True
            )
            
            # Generate CSR
            subprocess.run([
                'openssl', 'req', '-new',
                '-key', str(key_file),
                '-out', str(csr_file),
                '-subj', '/C=US/ST=CA/L=SF/O=PrinterServer/CN=SF-Printer-Server'
            ], check=True, capture_output=True)
            
            # Generate self-signed certificate (2 years)
            subprocess.run([
                'openssl', 'x509', '-req',
                '-days', '730',
                '-in', str(csr_file),
                '-signkey', str(key_file),
                '-out', str(cert_file)
            ], check=True, capture_output=True)
            
            # Set secure permissions
            key_file.chmod(0o600)
            
            # Clean up CSR
            csr_file.unlink(missing_ok=True)
            
            return {
                'key_file': key_file,
                'cert_file': cert_file
            }
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to generate certificate: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error generating certificate: {e}")
            return None
    
    def _prompt_instance_type(self) -> str:
        """Prompt for Salesforce instance type."""
        print("\nSelect your Salesforce instance type:")
        print("  1. Production (login.salesforce.com)")
        print("  2. Sandbox (test.salesforce.com)")
        print("  3. Custom Domain")
        
        choice = input("\nChoice (1-3): ").strip()
        
        if choice == '1':
            return 'https://login.salesforce.com'
        elif choice == '2':
            return 'https://test.salesforce.com'
        elif choice == '3':
            domain = input("Enter your custom domain (e.g., https://mydomain.my.salesforce.com): ").strip()
            return domain.rstrip('/')
        else:
            print("Invalid choice, using production.")
            return 'https://login.salesforce.com'
    
    def _print_connected_app_instructions(self, cert_file: Path):
        """Print detailed Connected App setup instructions."""
        print("\n📋 CONNECTED APP SETUP INSTRUCTIONS")
        print("\n1. In Salesforce, go to:")
        print("   Setup → App Manager → New Connected App")
        
        print("\n2. Fill in basic information:")
        print("   • Connected App Name: Printer Server")
        print("   • API Name: Printer_Server")
        print("   • Contact Email: (your email)")
        
        print("\n3. Enable OAuth Settings:")
        print("   ✓ Enable OAuth Settings")
        print("   • Callback URL: https://login.salesforce.com")
        print("   ✓ Use digital signatures (IMPORTANT!)")
        print(f"   • Upload this file: {cert_file}")
        
        print("\n4. Selected OAuth Scopes (add these):")
        print("   • Access and manage your data (api)")
        print("   • Perform requests on your behalf at any time (refresh_token, offline_access)")
        
        print("\n5. Click 'Save' and wait 2-10 minutes for changes to take effect")
        
        print("\n6. After saving, click 'Manage' → 'Edit Policies':")
        print("   • Permitted Users: 'Admin approved users are pre-authorized'")
        print("   • Save")
        
        print("\n7. Click 'Manage Profiles' or 'Manage Permission Sets':")
        print("   • Add your integration user's profile/permission set")
    
    def _save_config(self):
        """Save configuration to file."""
        from sf_printer_server.config.manager import ConfigManager
        
        config_mgr = ConfigManager()
        
        for key, value in self.config.items():
            config_mgr.set(key, value)
        
        config_mgr.save()
    
    def _test_authentication(self) -> bool:
        """Test authentication with saved config."""
        try:
            from sf_printer_server.config.manager import ConfigManager
            from sf_printer_server.auth.manager import AuthManager
            
            config_mgr = ConfigManager()
            auth_mgr = AuthManager(config_mgr)
            
            return auth_mgr.initialize()
        except Exception as e:
            logger.error(f"Authentication test failed: {e}")
            return False
    
    def _print_completion(self):
        """Print completion message."""
        print("\n" + "="*70)
        print(" " * 20 + "SETUP COMPLETE!")
        print("="*70)
        print("\n✅ Salesforce Printer Server is now configured!")
        
        print("\nNext steps:")
        print("  1. Set up custom objects in Salesforce:")
        print("     sf-printer-server salesforce deploy")
        print("\n  2. Test authentication:")
        print("     sf-printer-server auth test")
        print("\n  3. Start the server:")
        print("     sf-printer-server start")
        
        print("\nFor help:")
        print("  sf-printer-server --help")
        print("\nDocumentation:")
        print("  ~/.sf_printer_server/docs/")
        print("\n" + "="*70 + "\n")


def prompt_for_salesforce_setup():
    """Legacy function for backward compatibility."""
    installer = PrinterServerInstaller()
    installer.run()


def main():
    """Run installer from command line."""
    if len(sys.argv) > 1 and sys.argv[1] == '--help':
        print("Salesforce Printer Server Installer")
        print("\nUsage: python installer.py")
        print("       sf-printer-server install")
        print("\nThis interactive wizard will guide you through:")
        print("  • JWT certificate generation")
        print("  • Connected App setup in Salesforce")
        print("  • Authentication configuration")
        return
    
    installer = PrinterServerInstaller()
    installer.run()


if __name__ == "__main__":
    main()