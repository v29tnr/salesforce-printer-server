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
    
    # Stop the running service to free up port 8888
    echo "Stopping service temporarily to free port 8888..."
    $DOCKER_COMPOSE down 2>/dev/null
    
    # Run the auth script inside a temporary container
    # Map port 8888 for OAuth callback and run interactively
    # Set SSH_CONNECTION env var to trigger headless mode
    echo ""
    $DOCKER_COMPOSE run --rm --service-ports -e SSH_CONNECTION=true sf-printer-server python3 /app/src/sf_printer_server/auth_setup.py
    
    AUTH_RESULT=$?
    
    # Restart the service
    if [ $AUTH_RESULT -eq 0 ]; then
        echo ""
        echo "Starting service..."
        $DOCKER_COMPOSE up -d
    else
        echo ""
        echo "Authentication failed. Start service manually with: make start"
    fi
    
    exit $AUTH_RESULT
fi
