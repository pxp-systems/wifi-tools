# Raspberry Pi 5 — Automated Guest Wi-Fi Password Updater

This project automates guest Wi-Fi password rotation for your Huawei WiFi AX3 router and sends the new password to you via Telegram. It now features:
- **Secrets managed via a `.env` file** (never committed to git)
- **Split scripts:**
  - `batch.py`: Rotates the password and sends it via Telegram
  - `reset_listener.py`: Listens for Telegram `/reset` commands to trigger a password reset
- **Shared helpers in `wifi_utils.py`**

## 🚀 Quick Start

### 1. Clone and Setup
```bash
git clone <your-repo-url>
cd wifi-automation
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
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
