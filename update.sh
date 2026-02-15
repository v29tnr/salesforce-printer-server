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

# Determine which docker compose command to use
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
elif docker compose version &> /dev/null 2>&1; then
    DOCKER_COMPOSE="docker compose"
else
    echo "❌ docker-compose not found"
    exit 1
fi

# Stop service
echo "🛑 Stopping service..."
$DOCKER_COMPOSE down

# Rebuild image
echo "🏗️  Rebuilding Docker image..."
$DOCKER_COMPOSE build --no-cache

# Start service
echo "🚀 Starting service..."
$DOCKER_COMPOSE up -d --force-recreate

echo ""
echo -e "${GREEN}✅ Update complete!${NC}"
echo ""
echo "View logs: docker compose logs -f"
