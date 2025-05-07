# Love Restaurant Bot Installation Script for Windows

Write-Host "Love Restaurant Bot Installation" -ForegroundColor Green
Write-Host "This script will set up and run the Love Restaurant Bot"
Write-Host ""

# Check if .env already exists
if (Test-Path .env) {
    Write-Host "Existing .env file found" -ForegroundColor Yellow
    $recreateEnv = Read-Host "Do you want to recreate it? (y/n)"
    if ($recreateEnv -eq "y" -or $recreateEnv -eq "Y") {
        Remove-Item .env
        New-Item -Path .env -ItemType File
        $setupEnv = $true
    } else {
        Write-Host "Keeping existing .env file"
    }
} else {
    New-Item -Path .env -ItemType File
    $setupEnv = $true
}

# Setup .env if needed
if ($setupEnv) {
    Write-Host "Setting up environment variables" -ForegroundColor Green
    
    # Get Telegram Bot Token
    $botToken = Read-Host "Enter your Telegram Bot Token (from @BotFather)"
    Add-Content -Path .env -Value "BOT_TOKEN=$botToken"
    
    # Get Admin Telegram ID
    $adminId = Read-Host "Enter your Telegram ID (for admin notifications)"
    Add-Content -Path .env -Value "ADMIN_ID=$adminId"
    
    # Get Admin Telegram Username
    $adminUsername = Read-Host "Enter your Telegram username without @ (for help button)"
    Add-Content -Path .env -Value "ADMIN_USERNAME=$adminUsername"
    
    # Get Boosty URL (optional)
    $boostyUrl = Read-Host "Enter your Boosty URL (leave empty if none)"
    if ($boostyUrl) {
        Add-Content -Path .env -Value "BOOSTY_URL=$boostyUrl"
    }
    
    Write-Host "Environment variables have been set up!" -ForegroundColor Green
}

# Check if Docker is installed
try {
    $dockerVersion = docker --version
    Write-Host "Docker is installed: $dockerVersion" -ForegroundColor Green
} catch {
    Write-Host "Docker is not installed on this system." -ForegroundColor Yellow
    Write-Host "Please install Docker Desktop before continuing."
    Write-Host "Visit https://docs.docker.com/desktop/windows/install/ for installation instructions."
    exit
}

# Check if Docker Compose is installed
try {
    $composeVersion = docker-compose --version
    Write-Host "Docker Compose is installed: $composeVersion" -ForegroundColor Green
} catch {
    Write-Host "Docker Compose is not installed on this system." -ForegroundColor Yellow
    Write-Host "Please install Docker Desktop with Docker Compose before continuing."
    Write-Host "Visit https://docs.docker.com/desktop/windows/install/ for installation instructions."
    exit
}

Write-Host "Starting Docker containers..." -ForegroundColor Green
docker-compose down
docker-compose up -d

Write-Host "Installation complete!" -ForegroundColor Green
Write-Host "The Love Restaurant Bot is now running!"
Write-Host ""
Write-Host "You can check the logs with: docker-compose logs -f"
Write-Host "To stop the bot: docker-compose down" 