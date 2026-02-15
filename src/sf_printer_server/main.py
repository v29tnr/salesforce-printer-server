import sys
import logging
from sf_printer_server.cli import CLI
from sf_printer_server.installer import Installer
from sf_printer_server.salesforce.cometd import CometDListener

def main():
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # Initialize the installer
    installer = Installer()
    if not installer.is_configured():
        installer.setup()

    # Start the CometD listener for platform events
    cometd_listener = CometDListener()
    cometd_listener.start()

    # Initialize the command-line interface
    cli = CLI()
    cli.run()

if __name__ == "__main__":
    main()