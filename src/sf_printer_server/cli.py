import argparse
import sys
import getpass
from pathlib import Path
from sf_printer_server.config.manager import ConfigManager


def get_config_path():
    """Get the active config file path (matching ConfigManager priority)."""
    if Path('/app/config/config.toml').exists():
        return Path('/app/config/config.toml')
    home_cfg = Path.home() / '.sf_printer_server' / 'config.toml'
    if home_cfg.exists():
        return home_cfg
    if Path('config.toml').exists():
        return Path('config.toml')
    # Default: Docker volume path
    return Path('/app/config/config.toml')


def _prompt(label: str, current: str = '', secret: bool = False) -> str:
    """Prompt user for a value, showing current (masked if secret). Empty input keeps current."""
    if current:
        display = ('*' * 6 + current[-4:]) if secret and len(current) > 4 else (('*' * 8) if secret else current)
        prompt_str = f"  {label} [{display}]: "
    else:
        prompt_str = f"  {label} (not set): "

    if secret:
        val = getpass.getpass(prompt_str)
    else:
        val = input(prompt_str).strip()

    return val if val else current


def run_setup(interactive: bool = True):
    """Interactive setup wizard for credentials."""
    config_path = get_config_path()

    # Bootstrap config file if it doesn't exist
    if not config_path.exists():
        from sf_printer_server.config import defaults as _defaults_mod
        import shutil
        default_cfg = Path(_defaults_mod.__file__).parent / 'defaults.toml'
        config_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(default_cfg, config_path)
        print(f"Created new config at: {config_path}")
    else:
        print(f"Editing config at: {config_path}")

    config = ConfigManager(str(config_path))

    def get(section, key):
        return (config.config.get(section) or {}).get(key, '')

    def set_val(section, key, value):
        if section not in config.config:
            config.config[section] = {}
        config.config[section][key] = value

    print("\n=== Salesforce Auth Setup ===")
    print("Press Enter to keep the current value.\n")

    # --- Salesforce section ---
    instance_url = _prompt("Instance URL (e.g. https://myorg.my.salesforce.com)",
                           get('salesforce', 'instance_url'))
    set_val('salesforce', 'instance_url', instance_url)

    # --- Auth section ---
    client_id = _prompt("Connected App Consumer Key (client_id)",
                        get('auth', 'client_id'))
    set_val('auth', 'client_id', client_id)

    client_secret = _prompt("Connected App Consumer Secret (client_secret)",
                            get('auth', 'client_secret'), secret=True)
    set_val('auth', 'client_secret', client_secret)

    username = _prompt("Salesforce Username",
                       get('auth', 'username'))
    set_val('auth', 'username', username)

    streaming_password = _prompt("Password + Security Token (e.g. MyPass123TokenABC)",
                                 get('auth', 'streaming_password'), secret=True)
    set_val('auth', 'streaming_password', streaming_password)

    private_key_file = _prompt("Path to JWT private key file (leave blank if using password auth)",
                               get('auth', 'private_key_file'))
    set_val('auth', 'private_key_file', private_key_file)

    print()
    config.save_config()
    print("✓ Configuration saved.")
    print(f"  Config file: {config_path}")
    print("\nRestart the server to apply changes:")
    print("  docker-compose restart\n")

def main():
    parser = argparse.ArgumentParser(
        description='Salesforce Printer Server CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Interactive setup wizard
    subparsers.add_parser('setup', help='Interactive setup: configure Salesforce credentials')

    # Command to update configuration
    config_parser = subparsers.add_parser('config', help='Manage configuration settings')
    config_parser.add_argument('--client-id', type=str, help='Client ID for the connected app')
    config_parser.add_argument('--client-secret', type=str, help='Client secret for the connected app')
    config_parser.add_argument('--instance-url', type=str, help='Salesforce instance URL (e.g., https://your-domain.my.salesforce.com)')
    config_parser.add_argument('--api-version', type=str, help='Salesforce API version (e.g., 60.0)')
    config_parser.add_argument('--platform-event', type=str, help='Platform Event API name (without __e suffix)')
    config_parser.add_argument('--show', action='store_true', help='Show current configuration')

    # Command to display help
    help_parser = subparsers.add_parser('help', help='Display detailed help information')

    # Command to start the server
    start_parser = subparsers.add_parser('start', help='Start the printer server')

    # Command to check status
    status_parser = subparsers.add_parser('status', help='Check server status')

    args = parser.parse_args()

    if args.command == 'setup':
        run_setup()
    elif args.command == 'config':
        manage_config(args)
    elif args.command == 'help':
        display_help()
    elif args.command == 'start':
        start_server()
    elif args.command == 'status':
        check_status()
    else:
        parser.print_help()

def manage_config(args):
    """Manage configuration settings"""
    config_path = get_config_path()
    
    # Initialize config manager
    if not config_path.exists():
        # Copy default config
        from sf_printer_server.config import defaults
        import shutil
        default_config = Path(defaults.__file__).parent / 'defaults.toml'
        shutil.copy(default_config, config_path)
        print(f"Created new configuration file at: {config_path}")
    
    config_manager = ConfigManager(str(config_path))
    
    if args.show:
        print("\n=== Current Configuration ===")
        print(f"Configuration file: {config_path}")
        print("\n[Salesforce Settings]")
        print(f"  Instance URL: {config_manager.get('salesforce', {}).get('instance_url', 'Not set')}")
        print(f"  API Version: {config_manager.get('salesforce', {}).get('api_version', 'Not set')}")
        print(f"  Client ID: {config_manager.get('salesforce', {}).get('client_id', 'Not set')}")
        print(f"  Client Secret: {'*' * 10 if config_manager.get('salesforce', {}).get('client_secret') else 'Not set'}")
        print(f"  Platform Event: {config_manager.get('salesforce', {}).get('platform_event_name', 'Not set')}")
        print("\n[Printer Settings]")
        print(f"  Default Printer ID: {config_manager.get('printer', {}).get('default_printer_id', 'Not set')}")
        print(f"  ZPL Enabled: {config_manager.get('printer', {}).get('zpl_enabled', 'Not set')}")
        return
    
    updates = {}
    if not config_manager.config.get('salesforce'):
        config_manager.config['salesforce'] = {}
    
    if args.client_id:
        config_manager.config['salesforce']['client_id'] = args.client_id
        updates['client_id'] = args.client_id
    if args.client_secret:
        config_manager.config['salesforce']['client_secret'] = args.client_secret
        updates['client_secret'] = '***'
    if args.instance_url:
        config_manager.config['salesforce']['instance_url'] = args.instance_url
        updates['instance_url'] = args.instance_url
    if args.api_version:
        config_manager.config['salesforce']['api_version'] = args.api_version
        updates['api_version'] = args.api_version
    if args.platform_event:
        config_manager.config['salesforce']['platform_event_name'] = args.platform_event
        updates['platform_event_name'] = args.platform_event
    
    if updates:
        config_manager.save_config()
        print("\n✓ Configuration updated successfully!")
        for key, value in updates.items():
            print(f"  {key}: {value}")
    else:
        print("No configuration changes specified. Use --help to see available options.")

def display_help():
    """Display comprehensive help information"""
    help_text = """
╔══════════════════════════════════════════════════════════════════════════╗
║              SALESFORCE PRINTER SERVER - HELP GUIDE                      ║
╚══════════════════════════════════════════════════════════════════════════╝

OVERVIEW:
  The Salesforce Printer Server listens to Salesforce Platform Events and 
  processes print jobs using configured printers. It supports ZPL and 
  document printing.

COMMANDS:
  config              Manage configuration settings
  help                Display this help information
  start               Start the printer server
  status              Check server status

CONFIGURATION:
  sf-printer-server config [OPTIONS]
  
  Options:
    --client-id TEXT        Salesforce Connected App Client ID
    --client-secret TEXT    Salesforce Connected App Client Secret
    --instance-url TEXT     Salesforce instance URL 
                           (e.g., https://your-domain.my.salesforce.com)
    --api-version TEXT      Salesforce API version (e.g., 60.0)
    --platform-event TEXT   Platform Event API name (without __e suffix)
    --show                  Display current configuration

  Examples:
    sf-printer-server config --instance-url https://mycompany.my.salesforce.com
    sf-printer-server config --api-version 60.0
    sf-printer-server config --client-id 3MVG9... --client-secret ABC123...
    sf-printer-server config --show

INITIAL SETUP:
  1. Install the package:
     pip install salesforce-printer-server
  
  2. Run the installer:
     sf-printer-server-install
  
  3. Configure Salesforce settings:
     sf-printer-server config --instance-url <URL> --api-version <VERSION>
  
  4. Set Connected App credentials:
     sf-printer-server config --client-id <ID> --client-secret <SECRET>
  
  5. Start the server:
     sf-printer-server start

SALESFORCE SETUP:
  For detailed Salesforce setup instructions, see:
  https://github.com/your-repo/salesforce-printer-server/docs/SALESFORCE_SETUP.md

  Quick steps:
  1. Create a Connected App in Salesforce Setup
  2. Enable OAuth settings with appropriate scopes
  3. Create custom objects for Printers and Print Jobs
  4. Create a Platform Event for print job notifications
  5. Set up automation to publish Platform Events

SUPPORT:
  Documentation: https://github.com/your-repo/salesforce-printer-server
  Issues: https://github.com/your-repo/salesforce-printer-server/issues

"""
    print(help_text)

def start_server():
    """Start the printer server"""
    from sf_printer_server.main import run_server
    print("Starting Salesforce Printer Server...")
    run_server()

def check_status():
    """Check server status"""
    print("Checking server status...")
    # TODO: Implement status check
    print("Status check not yet implemented")

if __name__ == '__main__':
    main()