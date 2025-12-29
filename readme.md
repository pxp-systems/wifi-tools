# Raspberry Pi 5 — Automated Guest Wi-Fi Password Updater

This project automates guest Wi-Fi password rotation (Playwright) and sends the new password to you via Telegram. The primary entrypoint is `wifi.py`; other scripts simply delegate to it for cron/systemd use.

## 🚀 Quick Start

### 1. Clone and Setup
```bash
git clone https://github.com/pxp-systems/wifi-tools.git
cd wifi-tools
```

### 2. Configure Secrets
Create a `.env` file in the project root:
```
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
TELEGRAM_CHAT_IDS=7370373994,1234567890   # comma-separated
ROUTER_PASSWORD=your-router-password      # required
ROUTER_URL=https://orbilogin.com          # or your router URL
HEADLESS=true
```
Do **not** commit `.env` to git!

### 3. Automated Pi Configuration
Run the setup script to install dependencies, set up the virtual environment, install Playwright browsers, configure systemd, and reboot:
```bash
chmod +x setup_pi.sh
./setup_pi.sh
```

After reboot, the reset listener will run automatically at startup.

---

### (Manual) Run Once
```bash
source venv/bin/activate
python wifi.py
```

### (Manual) Run the Reset Listener (Telegram `/reset`)
```bash
source venv/bin/activate
python wifi.py --watch
```

### (Manual) Systemd Setup

If you want to set up systemd manually instead of using the script, create a service file:

```bash
sudo nano /etc/systemd/system/wifi-bot.service
```

Paste the following:

```
[Unit]
Description=WiFi Auto-Rotator Bot
After=network-online.target

[Service]
ExecStart=/home/admin/run-wifi.sh
WorkingDirectory=/home/admin
StandardOutput=append:/home/admin/wifi.log
StandardError=append:/home/admin/wifi.log
Restart=always
User=pi

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl enable wifi-bot.service
sudo systemctl start wifi-bot.service
```

Check status:

```bash
sudo systemctl status wifi-bot.service
```
