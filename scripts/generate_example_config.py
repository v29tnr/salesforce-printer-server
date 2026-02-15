import toml

def generate_example_config():
    config = {
        "salesforce": {
            "client_id": "<YOUR_CLIENT_ID>",
            "client_secret": "<YOUR_CLIENT_SECRET>",
            "username": "<YOUR_SALESFORCE_USERNAME>",
            "password": "<YOUR_SALESFORCE_PASSWORD>",
            "security_token": "<YOUR_SECURITY_TOKEN>",
            "instance_url": "<YOUR_INSTANCE_URL>"
        },
        "printer": {
            "default_printer": "<DEFAULT_PRINTER_NAME>",
            "zpl_enabled": True
        },
        "print_job": {
            "max_retries": 3,
            "retry_delay": 5
        }
    }

    with open('config.example.toml', 'w') as f:
        toml.dump(config, f)

if __name__ == "__main__":
    generate_example_config()