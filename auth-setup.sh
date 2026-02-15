#!/bin/bash
# Quick authentication setup script
# Opens browser for Salesforce login - no security token required!

cd "$(dirname "$0")"

echo ""
echo "=========================================="
echo "  Salesforce Authentication Setup"
echo "=========================================="
echo ""
echo "This will open your browser to authenticate with Salesforce."
echo "The token obtained will work with both REST API and Streaming API."
echo "No security token needed!"
echo ""

# Check if running in Docker or natively
if [ -f /.dockerenv ]; then
    echo "Running inside Docker container..."
    python3 /app/src/sf_printer_server/auth_setup.py
else
    echo "Running from host..."
    if command -v python3 &> /dev/null; then
        python3 src/sf_printer_server/auth_setup.py
    elif command -v python &> /dev/null; then
        python src/sf_printer_server/auth_setup.py
    else
        echo "❌ Python not found. Please install Python 3.9+"
        exit 1
    fi
fi
