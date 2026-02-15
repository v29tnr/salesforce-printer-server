#!/bin/bash
# Quick authentication setup script
# Opens browser for Salesforce login - no security token required!

cd "$(dirname "$0")"

echo ""
echo "=========================================="
echo "  Salesforce Authentication Setup"
echo "=========================================="
echo ""
echo "This will authenticate with Salesforce for Streaming API access."
echo "(JWT tokens don't work with Streaming API - need OAuth token)"
echo ""

# Check if running in Docker or natively
if [ -f /.dockerenv ]; then
    # Running inside Docker
    echo "Running inside Docker container..."
    python3 /app/src/sf_printer_server/auth_setup.py
else
    # Running from host - need to use Docker to run it
    echo "Running authentication via Docker..."
    
    # Check if docker-compose or docker compose is available
    if command -v docker-compose &> /dev/null; then
        DOCKER_COMPOSE="docker-compose"
    elif docker compose version &> /dev/null 2>&1; then
        DOCKER_COMPOSE="docker compose"
    else
        echo "❌ Docker Compose not found. Please install Docker Compose."
        exit 1
    fi
    
    # Run the auth script inside the container
    # Map port 8888 for OAuth callback and run interactively
    $DOCKER_COMPOSE run --rm --service-ports sf-printer-server python3 /app/src/sf_printer_server/auth_setup.py
fi
