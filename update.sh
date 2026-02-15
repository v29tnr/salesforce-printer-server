#!/bin/bash
# Update script for Salesforce Printer Server

set -e

BLUE='\033[0;34m'
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${BLUE}"
echo "=========================================="
echo "  Updating Salesforce Printer Server"
echo "=========================================="
echo -e "${NC}"

# Pull latest code
echo "📥 Pulling latest code..."
git pull

# Backup config
if [ -f "config/config.toml" ]; then
    echo "💾 Backing up configuration..."
    cp config/config.toml config/config.toml.backup
fi

# Stop service
echo "🛑 Stopping service..."
docker compose down

# Rebuild image
echo "🏗️  Rebuilding Docker image..."
docker build -t sf-printer-server .

# Start service
echo "🚀 Starting service..."
docker compose up -d

echo ""
echo -e "${GREEN}✅ Update complete!${NC}"
echo ""
echo "View logs: docker compose logs -f"
