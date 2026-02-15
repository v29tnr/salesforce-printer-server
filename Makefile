# Salesforce Printer Server - Quick Commands
# Usage: make <command>

.PHONY: help install update start stop restart logs config status clean

help:
	@echo "Salesforce Printer Server - Quick Commands"
	@echo ""
	@echo "Setup & Updates:"
	@echo "  make install    - First-time installation"
	@echo "  make update     - Pull latest code and rebuild"
	@echo ""
	@echo "Service Management:"
	@echo "  make start      - Start the service"
	@echo "  make stop       - Stop the service"
	@echo "  make restart    - Restart the service"
	@echo "  make logs       - View live logs"
	@echo "  make status     - Check service status"
	@echo ""
	@echo "Configuration:"
	@echo "  make config     - Edit configuration"
	@echo "  make clean      - Remove containers and images"

install:
	@chmod +x install.sh && ./install.sh

update:
	@chmod +x update.sh && ./update.sh

start:
	@docker compose up -d || docker-compose up -d

stop:
	@docker compose down || docker-compose down

restart:
	@docker compose restart || docker-compose restart

logs:
	@(docker compose logs --follow 2>/dev/null || docker-compose logs --follow || docker logs sf-printer-server --follow)

status:
	@docker compose ps || docker-compose ps

config:
	@nano config/config.toml

clean:
	@docker compose down --rmi all || docker-compose down --rmi all
	@docker system prune -f
