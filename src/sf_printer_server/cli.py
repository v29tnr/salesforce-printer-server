"""
sf-printer CLI

Commands
--------
sf-printer setup              Guided first-time setup (walks through Connected App creation)
sf-printer config             Show current configuration
sf-printer config [flags]     Set one or more config values without entering the full wizard
  --instance-url URL
  --client-id     KEY
  --client-secret SECRET
  --api-version   VER         (default: v65.0)
sf-printer verify             Test connection to Salesforce
sf-printer start              Start the print server
"""
import argparse
import sys
import getpass
from pathlib import Path
from sf_printer_server.config.manager import ConfigManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_config_path() -> Path:
    """Return the active config file path, preferring Docker volume → home → cwd."""
    if Path('/app/config/config.toml').exists():
        return Path('/app/config/config.toml')
    home_cfg = Path.home() / '.sf_printer_server' / 'config.toml'
    if home_cfg.exists():
        return home_cfg
    if Path('config.toml').exists():
        return Path('config.toml')
    # Default write location
    return Path.home() / '.sf_printer_server' / 'config.toml'


def _ensure_config(config_path: Path) -> ConfigManager:
    """Create a default config file if none exists, then load it."""
    if not config_path.exists():
        from sf_printer_server.config import defaults as _defaults_mod
        import shutil
        default_cfg = Path(_defaults_mod.__file__).parent / 'defaults.toml'
        config_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(default_cfg, config_path)
    return ConfigManager(str(config_path))


def _get(config: ConfigManager, section: str, key: str) -> str:
    return (config.config.get(section) or {}).get(key, '')


def _set(config: ConfigManager, section: str, key: str, value: str):
    if section not in config.config:
        config.config[section] = {}
    config.config[section][key] = value


def _prompt(label: str, current: str = '', secret: bool = False) -> str:
    """Prompt; empty input keeps current value."""
    if current:
        display = ('*' * 6 + current[-4:]) if (secret and len(current) > 4) else ('*' * 8 if secret else current)
        prompt_str = f'  {label} [{display}]: '
    else:
        prompt_str = f'  {label}: '
    val = getpass.getpass(prompt_str) if secret else input(prompt_str).strip()
    return val if val else current


def _mask(val: str) -> str:
    if not val:
        return '(not set)'
    if len(val) <= 8:
        return '*' * len(val)
    return val[:4] + '*' * (len(val) - 8) + val[-4:]


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_setup(_args):
    """Guided first-time setup with Connected App instructions."""
    config_path = get_config_path()
    is_new = not config_path.exists()
    config = _ensure_config(config_path)

    print()
    print('╔══════════════════════════════════════════════════════╗')
    print('║       Salesforce Printer Server — First-Time Setup   ║')
    print('╚══════════════════════════════════════════════════════╝')
    print()
    if is_new:
        print(f'  Config will be saved to: {config_path}')
    else:
        print(f'  Editing existing config:  {config_path}')
    print()

    print('─── Step 1 of 3 ── Salesforce Connected App ──────────────')
    print()
    print('  Create a Connected App in Salesforce (first time only):')
    print()
    print('  1. Setup → App Manager → New Connected App')
    print()
    print('  2. Basic Info:')
    print('       Connected App Name:  Printer Server')
    print('       API Name:            Printer_Server')
    print('       Contact Email:       (your email)')
    print()
    print('  3. Enable OAuth Settings:')
    print('       ✓  Enable OAuth Settings')
    print('       Callback URL:  https://localhost:8888/oauth/callback')
    print('       Scopes:        Full access (full)')
    print('                      Access the identity URL service (api)')
    print()
    print('  4. Flow Enablement (scroll down):')
    print('       ✓  Enable Authorization Code and Credentials Flow')
    print('       ✓  Enable Client Credentials Flow')
    print()
    print('  5. OAuth Policies:')
    print('       ✓  Require Secret for Web Server Flow')
    print('       ✓  Require Proof Key for Code Exchange (PKCE)')
    print()
    print('  6. Save — wait 2–10 minutes, then go back to the Connected App')
    print('     and click "Manage Consumer Details" to get your Key + Secret.')
    print()
    print('  No certificate upload. No username or password needed.')
    print()
    input('  Press Enter when you have your Consumer Key and Consumer Secret... ')
    print()

    print('─── Step 2 of 3 ── Salesforce Credentials ────────────────')
    print()
    instance_url = _prompt('Instance URL  (e.g. https://myorg.my.salesforce.com)',
                           _get(config, 'salesforce', 'instance_url'))
    client_id     = _prompt('Consumer Key  (from the Connected App)',
                            _get(config, 'auth', 'client_id'))
    client_secret = _prompt('Consumer Secret',
                            _get(config, 'auth', 'client_secret'), secret=True)

    _set(config, 'salesforce', 'instance_url', instance_url)
    _set(config, 'auth', 'client_id',     client_id)
    _set(config, 'auth', 'client_secret', client_secret)
    _set(config, 'auth', 'method',        'client_credentials')
    print()

    print('─── Step 3 of 3 ── Save & Verify ─────────────────────────')
    print()
    config.save_config()
    print(f'  ✓ Saved to {config_path}')
    print()

    _run_verify(config)

    print()
    print('  Start the server:')
    print('    sf-printer start')
    print()


_PROMPT = '__prompt__'  # sentinel: flag was given without a value → prompt the user


def _resolve(value: str, label: str, secret: bool = False) -> str:
    """If value is the prompt sentinel, ask the user interactively."""
    if value != _PROMPT:
        return value
    if secret:
        return getpass.getpass(f'  {label}: ')
    return input(f'  {label}: ').strip()


def cmd_config(args):
    """Show config or set individual values via flags."""
    config_path = get_config_path()
    config = _ensure_config(config_path)

    changed = False

    if args.instance_url is not None:
        val = _resolve(args.instance_url, 'Instance URL (e.g. https://myorg.my.salesforce.com)')
        _set(config, 'salesforce', 'instance_url', val)
        print(f'  instance_url  → {val}')
        changed = True
    if args.client_id is not None:
        val = _resolve(args.client_id, 'Consumer Key (Client ID)')
        _set(config, 'auth', 'client_id', val)
        print(f'  client_id     → {val}')
        changed = True
    if args.client_secret is not None:
        val = _resolve(args.client_secret, 'Consumer Secret', secret=True)
        _set(config, 'auth', 'client_secret', val)
        print(f'  client_secret → {_mask(val)}')
        changed = True
    if args.api_version is not None:
        val = _resolve(args.api_version, 'API Version (e.g. v65.0)')
        _set(config, 'salesforce', 'api_version', val)
        print(f'  api_version   → {val}')
        changed = True

    if changed:
        config.save_config()
        print(f'\n  ✓ Saved to {config_path}')
        print('  Restart the server to apply changes.')
    else:
        # No flags — print current config
        sf   = config.config.get('salesforce', {})
        auth = config.config.get('auth', {})
        print()
        print(f'  Config file   : {config_path}')
        print(f'  instance_url  : {sf.get("instance_url") or "(not set)"}')
        print(f'  api_version   : {sf.get("api_version", "v65.0")}')
        print(f'  client_id     : {auth.get("client_id") or "(not set)"}')
        print(f'  client_secret : {_mask(auth.get("client_secret", ""))}')
        print(f'  auth_method   : {auth.get("method", "client_credentials")}')
        print()
        print('  To update (prompts for value if omitted):')
        print('    sf-printer config --client-id')
        print('    sf-printer config --client-secret')
        print('    sf-printer config --instance-url')
        print()


def cmd_verify(_args):
    config_path = get_config_path()
    config = _ensure_config(config_path)
    _run_verify(config)


def _run_verify(config: ConfigManager):
    """Test OAuth client credentials and print result."""
    import requests
    instance_url  = _get(config, 'salesforce', 'instance_url').rstrip('/')
    client_id     = _get(config, 'auth', 'client_id')
    client_secret = _get(config, 'auth', 'client_secret')

    if not instance_url or not client_id or not client_secret:
        print('  ✗ Cannot verify — instance_url, client_id, and client_secret are all required.')
        print('    Run:  sf-printer setup')
        return

    print('  Connecting to Salesforce... ', end='', flush=True)
    try:
        resp = requests.post(
            f'{instance_url}/services/oauth2/token',
            data={
                'grant_type':    'client_credentials',
                'client_id':     client_id,
                'client_secret': client_secret,
            },
            timeout=15,
        )
        if resp.status_code == 200:
            print('✓ Connected!')
        else:
            body = resp.json() if resp.headers.get('content-type', '').startswith('application/json') else resp.text
            err  = body.get('error_description', body) if isinstance(body, dict) else body
            print(f'✗ Failed ({resp.status_code}): {err}')
    except Exception as exc:
        print(f'✗ Error: {exc}')


def cmd_start(_args):
    from sf_printer_server.main import main as run_main
    print('Starting Salesforce Printer Server...')
    run_main()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        prog='sf-printer',
        description='Salesforce Printer Server',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest='command')

    # setup
    sub.add_parser('setup',  help='Guided first-time setup')

    # config
    p_cfg = sub.add_parser('config', help='Show or update configuration')
    p_cfg.add_argument('--instance-url',  dest='instance_url',  nargs='?', const=_PROMPT, metavar='URL',
                       help='Salesforce My Domain URL (omit value to be prompted)')
    p_cfg.add_argument('--client-id',     dest='client_id',     nargs='?', const=_PROMPT, metavar='KEY',
                       help='Consumer Key (omit value to be prompted)')
    p_cfg.add_argument('--client-secret', dest='client_secret', nargs='?', const=_PROMPT, metavar='SECRET',
                       help='Consumer Secret (omit value to be prompted securely)')
    p_cfg.add_argument('--api-version',   dest='api_version',   nargs='?', const=_PROMPT, metavar='VER',
                       help='Salesforce API version, e.g. v65.0 (omit value to be prompted)')

    # verify
    sub.add_parser('verify', help='Test Salesforce connection')

    # start
    sub.add_parser('start',  help='Start the print server')

    args = parser.parse_args()

    if   args.command == 'setup':  cmd_setup(args)
    elif args.command == 'config': cmd_config(args)
    elif args.command == 'verify': cmd_verify(args)
    elif args.command == 'start':  cmd_start(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()