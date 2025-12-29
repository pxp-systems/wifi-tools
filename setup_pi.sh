#!/bin/bash
set -e

# 1. Update and upgrade system packages
echo "Updating system packages..."
sudo apt update && sudo apt upgrade -y

# 2. Install Python 3, venv, pip, git if not present
echo "Installing Python3, venv, pip, git, xvfb..."
sudo apt install -y python3 python3-venv python3-pip git xvfb

# 3. Create and activate Python virtual environment
VENV_DIR="venv"
VENV_BIN="$VENV_DIR/bin"

if [ ! -d "$VENV_DIR" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv "$VENV_DIR"
fi
source "$VENV_BIN/activate"

# 4. Install Python dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# 5. Install Playwright browsers
echo "Installing Playwright browsers..."
"$VENV_BIN/python" -m playwright install chromium

# 6. Create systemd service for the reset listener
echo "Setting up systemd service..."
SERVICE_FILE="/etc/systemd/system/wifi-bot.service"
STATE_DIR="/var/lib/wifi-automation"
sudo mkdir -p "$STATE_DIR"
sudo chown "$(whoami)":"$(whoami)" "$STATE_DIR"
SERVICE_CONTENT="[Unit]\nDescription=WiFi Auto-Rotator Bot\nAfter=network-online.target\n\n[Service]\nEnvironmentFile=-$(pwd)/.env\nEnvironment=STATE_DIR=$STATE_DIR\nExecStart=/usr/bin/xvfb-run --auto-servernum --server-args=\\\"-screen 0 1280x800x24\\\" $(pwd)/$VENV_BIN/python $(pwd)/wifi.py --watch\nWorkingDirectory=$(pwd)\nStandardOutput=append:$(pwd)/wifi.log\nStandardError=append:$(pwd)/wifi.log\nRestart=always\nUser=$(whoami)\n\n[Install]\nWantedBy=multi-user.target\n"
echo -e "$SERVICE_CONTENT" | sudo tee $SERVICE_FILE

sudo systemctl daemon-reload
sudo systemctl enable wifi-bot.service
sudo systemctl restart wifi-bot.service

echo "Setup complete. The wifi-bot service is running and will start on boot."

# 7. Add daily cron job for Wi-Fi reset at 7:30am
CRONLINE="30 7 * * * cd $(pwd) && $(pwd)/$VENV_BIN/python $(pwd)/cron_daily_reset.py >> $(pwd)/cron_daily_reset.log 2>&1"
# Remove any existing line for cron_daily_reset.py to avoid duplicates
(crontab -l | grep -v 'cron_daily_reset.py'; echo "$CRONLINE") | crontab -
echo "Daily cron job added: $CRONLINE"

echo "Rebooting in 5 seconds... Press Ctrl+C to cancel."
sleep 5
sudo reboot
