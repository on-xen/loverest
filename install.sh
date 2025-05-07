#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Love Restaurant Bot Installation${NC}"
echo "This script will set up and run the Love Restaurant Bot"
echo ""

# Check if .env already exists
if [ -f .env ]; then
    echo -e "${YELLOW}Existing .env file found${NC}"
    read -p "Do you want to recreate it? (y/n): " recreate_env
    if [[ $recreate_env != "y" && $recreate_env != "Y" ]]; then
        echo "Keeping existing .env file"
    else
        rm .env
        touch .env
        setup_env=true
    fi
else
    touch .env
    setup_env=true
fi

# Setup .env if needed
if [ "$setup_env" = true ]; then
    echo -e "${GREEN}Setting up environment variables${NC}"
    
    # Get Telegram Bot Token
    read -p "Enter your Telegram Bot Token (from @BotFather): " bot_token
    echo "BOT_TOKEN=${bot_token}" >> .env
    
    # Get Admin Telegram ID
    read -p "Enter your Telegram ID (for admin notifications): " admin_id
    echo "ADMIN_ID=${admin_id}" >> .env
    
    # Get Admin Telegram Username
    read -p "Enter your Telegram username without @ (for help button): " admin_username
    echo "ADMIN_USERNAME=${admin_username}" >> .env
    
    # Get Boosty URL (optional)
    read -p "Enter your Boosty URL (leave empty if none): " boosty_url
    if [ ! -z "$boosty_url" ]; then
        echo "BOOSTY_URL=${boosty_url}" >> .env
    fi
    
    echo -e "${GREEN}Environment variables have been set up!${NC}"
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}Docker is not installed on this system.${NC}"
    echo "Please install Docker and Docker Compose before continuing."
    echo "Visit https://docs.docker.com/get-docker/ for installation instructions."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo -e "${YELLOW}Docker Compose is not installed on this system.${NC}"
    echo "Please install Docker Compose before continuing."
    echo "Visit https://docs.docker.com/compose/install/ for installation instructions."
    exit 1
fi

echo -e "${GREEN}Starting Docker containers...${NC}"
docker-compose down
docker-compose up -d

echo -e "${GREEN}Installation complete!${NC}"
echo "The Love Restaurant Bot is now running!"
echo ""
echo "You can check the logs with: docker-compose logs -f"
echo "To stop the bot: docker-compose down" 