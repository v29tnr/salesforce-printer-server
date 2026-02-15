#!/bin/bash
# One-command installer for Salesforce Printer Server

set -e

BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "=========================================="
echo "  Salesforce Printer Server Installer"
echo "=========================================="
echo -e "${NC}"

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found. Installing Docker...${NC}"
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    echo -e "${GREEN}✓ Docker installed. Please log out and back in, then run this script again.${NC}"
    exit 0
fi

# Check Docker permissions
if ! docker ps &> /dev/null; then
    echo -e "${YELLOW}⚠️  Adding user to docker group...${NC}"
    sudo usermod -aG docker $USER
    echo -e "${GREEN}✓ Added to docker group. Activating...${NC}"
    newgrp docker << EONG
        bash $0 "$@"
EONG
    exit 0
fi

# Check docker-compose
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Installing docker-compose...${NC}"
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    echo -e "${GREEN}✓ docker-compose installed${NC}"
fi

# Determine which docker compose command to use
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
elif docker compose version &> /dev/null 2>&1; then
    DOCKER_COMPOSE="docker compose"
else
    echo -e "${RED}❌ Failed to install docker-compose${NC}"
    exit 1
fi

# Create directories
echo -e "${BLUE}📁 Creating directories...${NC}"
mkdir -p config certs

# Interactive configuration
echo ""
echo -e "${BLUE}=========================================="
echo "  Configuration Setup"
echo "==========================================${NC}"
echo ""

# Salesforce instance
echo -e "${YELLOW}Select Salesforce instance type:${NC}"
echo "  1. Production (login.salesforce.com)"
echo "  2. Sandbox (test.salesforce.com)"
echo "  3. Custom domain"
read -p "Choice [1]: " instance_choice
instance_choice=${instance_choice:-1}

case $instance_choice in
    2) INSTANCE_URL="https://test.salesforce.com" ;;
    3) 
        read -p "Enter your custom domain: " custom_domain
        INSTANCE_URL="${custom_domain}"
        ;;
    *) INSTANCE_URL="https://login.salesforce.com" ;;
esac

# Auth method
echo ""
echo -e "${YELLOW}Select authentication method:${NC}"
echo "  1. JWT (Recommended for production)"
echo "  2. Username/Password (Testing only)"
read -p "Choice [1]: " auth_choice
auth_choice=${auth_choice:-1}

if [ "$auth_choice" = "1" ]; then
    AUTH_METHOD="jwt"
    
    # Generate certificates
    echo ""
    echo -e "${BLUE}🔐 Generating SSL certificates...${NC}"
    cd certs
    openssl genrsa -out private_key.pem 2048 2>/dev/null
    openssl req -new -x509 -key private_key.pem -out certificate.crt -days 730 \
        -subj "/C=US/ST=CA/L=SF/O=PrinterServer/CN=SF-Printer-Server" 2>/dev/null
    chmod 600 private_key.pem
    cd ..
    echo -e "${GREEN}✓ Certificates generated in ./certs/${NC}"
    
    # Show Connected App instructions
    echo ""
    echo -e "${BLUE}=========================================="
    echo "  Salesforce Connected App Setup"
    echo "==========================================${NC}"
    echo ""
    echo "Please create a Connected App in Salesforce:"
    echo ""
    echo "1. Go to: Setup → App Manager → New Connected App"
    echo "2. Fill in:"
    echo "   • Name: Printer Server"
    echo "   • API Name: Printer_Server"
    echo "   • Contact Email: (your email)"
    echo ""
    echo "3. Enable OAuth Settings:"
    echo "   ✓ Enable OAuth Settings"
    echo "   • Callback URL: ${INSTANCE_URL}"
    echo ""
    echo "4. Flow Enablement (scroll down):"
    echo "   ✓ Enable JWT Bearer Flow"
    echo "   • Upload Certificate (OR copy/paste below)"
    echo ""
    echo -e "${YELLOW}=========================================="
    echo "  CERTIFICATE (Copy this entire block)"
    echo "==========================================${NC}"
    cat certs/certificate.crt
    echo -e "${YELLOW}=========================================="
    echo "  (End of certificate)"
    echo "==========================================${NC}"
    echo ""
    echo "5. OAuth Scopes:"
    echo "   • Access and manage your data (api)"
    echo "   • Perform requests on your behalf at any time (refresh_token, offline_access)"
    echo ""
    echo "6. Click 'Save' and wait 2-10 minutes for changes to take effect"
    echo ""
    echo -e "${GREEN}Note: For JWT authentication, 'Permitted Users' will be greyed out - this is normal!"
    echo "JWT uses server-to-server authentication and doesn't require user approval.${NC}"
    echo ""
    echo "7. Ensure your integration user has API access in Salesforce"
    echo ""
    
    read -p "Press ENTER when ready to continue..."
    
    read -p "Consumer Key: " CLIENT_ID
    read -p "Integration user email: " USERNAME
    
    PRIVATE_KEY_FILE="/app/certs/private_key.pem"
    
else
    AUTH_METHOD="password"
    
    echo ""
    read -p "Consumer Key: " CLIENT_ID
    read -p "Consumer Secret: " CLIENT_SECRET
    read -p "Username: " USERNAME
    read -sp "Password: " PASSWORD
    echo ""
    read -p "Security Token: " SECURITY_TOKEN
    FULL_PASSWORD="${PASSWORD}${SECURITY_TOKEN}"
fi


# Create config file
echo ""
echo -e "${BLUE}📝 Creating configuration file...${NC}"

cat > config/config.toml << EOF
# Salesforce Printer Server Configuration

[salesforce]
instance_url = "${INSTANCE_URL}"

[auth]
method = "${AUTH_METHOD}"
client_id = "${CLIENT_ID}"
username = "${USERNAME}"
EOF

if [ "$AUTH_METHOD" = "jwt" ]; then
    cat >> config/config.toml << EOF
private_key_file = "${PRIVATE_KEY_FILE}"
EOF
else
    cat >> config/config.toml << EOF
client_secret = "${CLIENT_SECRET}"
password = "${FULL_PASSWORD}"
EOF
fi

cat >> config/config.toml << EOF

[logging]
level = "INFO"
EOF

chmod 600 config/config.toml

echo -e "${GREEN}✓ Configuration saved${NC}"

# Build Docker image
echo ""
echo -e "${BLUE}🐋 Building Docker image...${NC}"
$DOCKER_COMPOSE build --no-cache

# Start service
echo ""
echo -e "${BLUE}🚀 Starting service...${NC}"
$DOCKER_COMPOSE up -d --force-recreate

# Wait a moment
sleep 2

# Check status
if docker ps | grep -q sf-printer-server; then
    echo ""
    echo -e "${GREEN}=========================================="
    echo "  ✅ Installation Complete!"
    echo "==========================================${NC}"
    echo ""
    echo "Service is running!"
    echo ""
    echo "Useful commands:"
    echo "  • View logs:    $DOCKER_COMPOSE logs -f"
    echo "  • Stop service: $DOCKER_COMPOSE down"
    echo "  • Restart:      $DOCKER_COMPOSE restart"
    echo "  • Status:       $DOCKER_COMPOSE ps"
    echo ""
else
    echo ""
    echo -e "${YELLOW}⚠️  Service may not have started correctly${NC}"
    echo "Check logs with: $DOCKER_COMPOSE logs"
fi
