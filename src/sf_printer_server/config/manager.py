from pathlib import Path
import toml
import json

class ConfigManager:
    def __init__(self, config_file: str):
        self.config_file = Path(config_file)
        self.config = {}
        self.load_config()

    def load_config(self):
        if self.config_file.exists():
            if self.config_file.suffix == '.toml':
                self.config = toml.load(self.config_file)
            elif self.config_file.suffix == '.json':
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
        else:
            raise FileNotFoundError(f"Configuration file {self.config_file} not found.")

    def save_config(self):
        if self.config_file.suffix == '.toml':
            with open(self.config_file, 'w') as f:
                toml.dump(self.config, f)
        elif self.config_file.suffix == '.json':
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=4)

    def get(self, key: str, default=None):
        return self.config.get(key, default)

    def set(self, key: str, value):
        self.config[key] = value
        self.save_config()

    def update(self, updates: dict):
        self.config.update(updates)
        self.save_config()