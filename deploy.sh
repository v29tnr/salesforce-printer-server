#!/bin/bash
# Deployment script for Salesforce Printer Server

set -e

echo "=========================================="
echo "Salesforce Printer Server Deployment"
echo "=========================================="

# Check if docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if running with proper permissions
if ! docker ps &> /dev/null; then
    echo "⚠️  Cannot access Docker daemon."
    echo "Either run with sudo or add your user to docker group:"
    echo "  sudo usermod -aG docker $USER"
    echo "  newgrp docker"
    exit 1
fi

# Create directories if they don't exist
echo ""
echo "Creating configuration directories..."
mkdir -p config
mkdir -p certs

# Check if config exists
if [ ! -f "config/config.toml" ]; then
    echo ""
    echo "⚠️  No configuration file found."
    if [ -f "examples/config.example.toml" ]; then
        echo "Copying example configuration..."
        cp examples/config.example.toml config/config.toml
        echo "✓ Configuration template created at: config/config.toml"
        echo ""
        echo "⚠️  IMPORTANT: Edit config/config.toml with your Salesforce credentials before starting!"
    else
        echo "❌ Example configuration not found. Please create config/config.toml manually."
    fi
fi

# Build the Docker image
echo ""
echo "Building Docker image..."
docker build -t sf-printer-server .

echo ""
echo "✓ Build complete!"
echo ""
echo "=========================================="
echo "Next Steps:"
echo "=========================================="
echo ""
echo "1. Edit your configuration:"
echo "   nano config/config.toml"
echo ""
echo "2. If using JWT authentication, place your certs in:"
echo "   ./certs/private_key.pem"
echo "   ./certs/certificate.crt"
echo ""
echo "3. Start the server:"
echo "   docker-compose up -d"
echo ""
echo "4. View logs:"
echo "   docker-compose logs -f"
echo ""
echo "5. Stop the server:"
echo "   docker-compose down"
echo ""
echo "=========================================="
