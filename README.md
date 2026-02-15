# Salesforce Printer Server

## Overview
The Salesforce Printer Server is a robust application designed to manage print jobs and printers using Salesforce's platform events. It listens for print job events via the CometD protocol and interacts with custom Salesforce objects for printers and print jobs.

## Features
- Listens to platform events for print jobs.
- Supports ZPL (Zebra Programming Language) for print job content.
- Managed via a command-line interface for easy configuration and updates.
- Utilizes OAuth for secure authentication with Salesforce.
- Configurable through a TOML file with default settings provided.

## Installation
1. **Clone the repository:**
   ```
   git clone <repository-url>
   cd salesforce-printer-server
   ```

2. **Install dependencies:**
   ```
   pip install -r requirements.txt
   ```

3. **Run the installer:**
   ```
   python src/sf_printer_server/installer.py
   ```
   Follow the prompts to set up your Salesforce connected app and configure the server.

## Configuration
The configuration file is located at `src/sf_printer_server/config/defaults.toml`. You can customize settings such as:
- Salesforce client ID and secret
- Printer settings
- Print job processing options

## Command Line Interface
The application provides a command-line interface for managing the printer server. Use the following command to access help:
```
python src/sf_printer_server/cli.py help
```

## Documentation
For detailed setup instructions and usage, refer to the documentation in the `docs` directory:
- [General Documentation](docs/README.md)
- [Salesforce Setup Instructions](docs/SALESFORCE_SETUP.md)

## Contributing
Contributions are welcome! Please submit a pull request or open an issue for any enhancements or bug fixes.

## License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.