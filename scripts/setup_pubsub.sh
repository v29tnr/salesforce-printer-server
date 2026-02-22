#!/bin/bash
# Setup script for Pub/Sub API

set -e

echo "========================================="
echo "Pub/Sub API Setup"
echo "========================================="
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed."
    exit 1
fi

echo "✓ Python 3 found"

# Install dependencies
echo ""
echo "Installing dependencies..."
pip3 install grpcio grpcio-tools avro-python3 certifi requests

echo "✓ Dependencies installed"

# Generate stub files
echo ""
echo "Generating gRPC stub files..."
python3 scripts/generate_stubs.py

echo ""
echo "========================================="
echo "Setup complete!"
echo "========================================="
echo ""
echo "The Pub/Sub API client is now ready to use."
echo ""
echo "To run the server:"
echo "  python3 -m sf_printer_server.main"
echo ""
