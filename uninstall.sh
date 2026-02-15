#!/bin/bash
# Uninstall script for Salesforce Printer Server

set -e

RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${RED}"
echo "=========================================="
echo "  Uninstall Salesforce Printer Server"
echo "=========================================="
echo -e "${NC}"

read -p "This will remove the service and optionally delete data. Continue? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Cancelled."
    exit 0
fi

# Stop and remove containers
echo "🛑 Stopping containers..."
docker-compose down

# Remove image
echo "🗑️  Removing Docker image..."
docker rmi sf-printer-server 2>/dev/null || true

# Ask about data
read -p "Delete configuration and certificates? (yes/no): " delete_data

if [ "$delete_data" = "yes" ]; then
    echo "🗑️  Removing data..."
    rm -rf config certs
    echo -e "${GREEN}✓ Data removed${NC}"
fi

echo ""
echo -e "${GREEN}✅ Uninstall complete${NC}"
