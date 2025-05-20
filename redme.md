# Raspberry Pi 5 — Automated Guest Wi-Fi Password Updater

This script logs into your Huawei WiFi AX3 router nightly, changes the guest Wi-Fi password to a simple TV-remote-friendly value, and sends it to you via Telegram.

## 🔧 Prerequisites

Run these commands from your Pi 5 terminal.

### 1. System Update & Python Setup
sudo apt update && sudo apt upgrade -y
sudo apt install python3-venv curl git -y


### 2. Python env
python3 -m venv ~/wifi-env
source ~/wifi-env/bin/activate

### 3. Playwright and requests
pip install --upgrade pip
pip install playwright requests
playwright install


### 4 install script
nano ~/run-wifi.sh

paste this
#!/bin/bash
source ~/wifi-env/bin/activate
python ~/wifi.py --watch

### Make executable and test
chmod +x ~/run-wifi.sh

./run-wifi.sh

### 5. Run at Boot with systemd

Create a service file:

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
User=admin

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
