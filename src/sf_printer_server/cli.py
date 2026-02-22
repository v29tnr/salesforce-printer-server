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
    """Interactive setup wizard — prompts for instance URL, client ID, and client secret."""
    config_path = get_config_path()

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

    print("\n=== Salesforce Printer Server Setup ===")
    print("Press Enter to keep the current value.\n")
    print("Requires a Connected App with 'Client Credentials Flow' enabled and a Run As user set.\n")

    instance_url = _prompt("Instance URL (e.g. https://myorg.my.salesforce.com)",
                           get('salesforce', 'instance_url'))
    set_val('salesforce', 'instance_url', instance_url)

    client_id = _prompt("Connected App Consumer Key (client_id)",
                        get('auth', 'client_id'))
    set_val('auth', 'client_id', client_id)

    client_secret = _prompt("Connected App Consumer Secret (client_secret)",
                            get('auth', 'client_secret'), secret=True)
    set_val('auth', 'client_secret', client_secret)

    set_val('auth', 'method', 'client_credentials')

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

    subparsers.add_parser('setup', help='Interactive setup: configure Salesforce credentials')
    subparsers.add_parser('start', help='Start the printer server')
    subparsers.add_parser('status', help='Check server status')

    args = parser.parse_args()

    if args.command == 'setup':
        run_setup()
    elif args.command == 'start':
        start_server()
    elif args.command == 'status':
        check_status()
    else:
        parser.print_help()


def start_server():
    from sf_printer_server.main import main as run_main
    print("Starting Salesforce Printer Server...")
    run_main()


def check_status():
    print("Status check not yet implemented")


if __name__ == '__main__':
    main()