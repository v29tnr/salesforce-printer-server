# Salesforce Printer Server

## Overview
The Salesforce Printer Server is a robust application designed to manage print jobs and printers using Salesforce's platform events. It listens for print job events and processes them accordingly, allowing seamless integration with various printer types.

## Features
- Listens to platform events using CometD.
- Manages custom objects in Salesforce for printers and print jobs.
- Supports ZPL (Zebra Programming Language) for print jobs.
- Command-line interface for easy management and configuration.
- OAuth authentication via a connected app in Salesforce.

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
   Follow the prompts to configure your connected app in Salesforce.

## Configuration
The application uses a TOML configuration file. An example configuration can be found in `examples/config.example.toml`. You can customize the settings according to your environment.

## Usage
To start the server, run:
```
python src/sf_printer_server/main.py
```

## Command Line Interface
You can manage the printer server using the command line. Use the following command to display help:
```
python src/sf_printer_server/cli.py help
```

## Help
For detailed setup instructions specific to Salesforce, refer to `docs/SALESFORCE_SETUP.md`.

## Contributing
Contributions are welcome! Please submit a pull request or open an issue for any enhancements or bug fixes.

## License
This project is licensed under the MIT License. See the LICENSE file for more details.