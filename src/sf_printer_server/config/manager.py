from pathlib import Path
import toml
import json
import os


class ConfigManager:
    """Manages configuration loading and access."""
    
    def __init__(self, config_file: str = None):
        """
        Initialize ConfigManager.
        
        Args:
            config_file: Path to config file. If None, uses default locations.
        """
        if config_file is None:
            # Check for config in Docker volume mount first
            if Path('/app/config/config.toml').exists():
                config_file = '/app/config/config.toml'
            # Then check user home directory
            elif (Path.home() / '.sf_printer_server' / 'config.toml').exists():
                config_file = str(Path.home() / '.sf_printer_server' / 'config.toml')
            # Finally check current directory
            elif Path('config.toml').exists():
                config_file = 'config.toml'
            else:
                config_file = None
        
        self.config_file = Path(config_file) if config_file else None
        self.config = {}
        if self.config_file:
            self.load_config()

    def exists(self):
        """Check if config file exists."""
        return self.config_file and self.config_file.exists()

    def load_config(self):
        """Load configuration from file."""
        if not self.config_file or not self.config_file.exists():
            return
        
        if self.config_file.suffix == '.toml':
            self.config = toml.load(self.config_file)
        elif self.config_file.suffix == '.json':
            with open(self.config_file, 'r') as f:
                self.config = json.load(f)

    def save_config(self):
        """Save configuration to file."""
        if not self.config_file:
            raise ValueError("No config file specified")
        
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        
        if self.config_file.suffix == '.toml':
            with open(self.config_file, 'w') as f:
                toml.dump(self.config, f)
        elif self.config_file.suffix == '.json':
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=4)

    def get(self, key: str, default=None):
        """
        Get configuration value using dot notation.
        
        Args:
            key: Configuration key (e.g., 'salesforce.instance_url')
            default: Default value if key not found
        
        Returns:
            Configuration value or default
        """
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        
        return value

    def set(self, key: str, value):
        """
        Set configuration value using dot notation.
        
        Args:
            key: Configuration key (e.g., 'salesforce.instance_url')
            value: Value to set
        """
        keys = key.split('.')
        config = self.config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
        self.save_config()

    def update(self, updates: dict):
        """Update multiple configuration values."""
        self.config.update(updates)
        self.save_config()