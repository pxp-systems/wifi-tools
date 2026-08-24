# Raspberry Pi 5 — Automated Guest Wi-Fi Password Updater

This project automates guest Wi-Fi password rotation (Playwright) and sends the new password to you via Telegram. It can also enforce **downtime** — automatically switching the guest network off and back on to a time schedule. The primary entrypoint is `wifi.py`; other scripts simply delegate to it for cron/systemd use.

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
GUEST_SSID_SELECTOR=#ssid                  # optional: defaults to #ssid
HEADLESS=true
LAST_UPDATE_ID_FILE=~/.wifi-automation/last_telegram_update  # optional override

# Downtime — guest network off overnight (all optional)
DOWNTIME_ENABLED=true
DOWNTIME_START=22:30
DOWNTIME_END=06:30
DOWNTIME_DAYS=all                          # all | weekdays | weekends | mon,tue,fri
DOWNTIME_NOTIFY=true                       # Telegram message when it flips
GUEST_ENABLE_SELECTOR=#enable_guest        # "Enable Guest Network" checkbox
```
Guest SSID is automatically generated each run as `AG-DDMMYYhhmm`.
Do **not** commit `.env` to git!

### 3. Automated Pi Configuration
Run the setup script to install dependencies, set up the virtual environment, install Playwright browsers, configure systemd, and reboot:
```bash
chmod +x setup_pi.sh
./setup_pi.sh
```

After reboot, the reset listener will run automatically at startup.

---

## 🌙 Downtime (scheduled guest network off/on)

Set `DOWNTIME_ENABLED=true` and a window, and the guest network is switched **off** at
`DOWNTIME_START` and back **on** at `DOWNTIME_END`, in the Pi's local time.

```
DOWNTIME_ENABLED=true
DOWNTIME_START=22:30
DOWNTIME_END=06:30
DOWNTIME_DAYS=all
```

- Windows may cross midnight (`22:30`–`06:30`). `DOWNTIME_DAYS` filters on the day the
  window **starts**, so `DOWNTIME_DAYS=sun` with the window above covers Sunday 22:30
  through Monday 06:30.
- Enforcement is **state-based, not edge-triggered**. The last applied state is stored in
  `$STATE_DIR/guest_state`, and every check compares the schedule's wanted state against
  it — so a reboot, a crash, or a failed router login self-corrects on the next check
  rather than leaving the network stuck off.
- The `--watch` service (see systemd below) evaluates the schedule on every poll loop,
  i.e. roughly every 30 seconds. No extra cron entry is needed if that service is running.
- Password rotation is independent of downtime: a `/reset` or the daily cron job while the
  network is off updates the SSID/passphrase without switching it back on.

### Before first use: check the toggle selector

`GUEST_ENABLE_SELECTOR` defaults to `#enable_guest`, which may not match your firmware.
Confirm it with codegen and put the real selector in `.env`:

```bash
source venv/bin/activate
playwright codegen https://orbilogin.com
```

Then dry-run the toggle once each way:

```bash
python wifi.py --guest-off
python wifi.py --guest-on
```

On failure a screenshot is written to `fail-guest-network-off.png` / `fail-guest-network-on.png`.

### Manual and cron control

```bash
python wifi.py --guest-off        # switch guest network off now
python wifi.py --guest-on         # switch it back on now
python wifi.py --apply-schedule   # apply whatever the schedule wants right now
python wifi.py --apply-schedule --force   # re-apply even if the stored state matches
```

If you are **not** running the `--watch` service, drive the schedule from cron instead —
every 5 minutes is plenty, since `--apply-schedule` is a no-op when nothing needs to change:

```
*/5 * * * * cd /home/admin/wifi-tools && /home/admin/wifi-tools/venv/bin/python wifi.py --apply-schedule >> /home/admin/wifi-tools/downtime.log 2>&1
```

Manual `--guest-on`/`--guest-off` while `DOWNTIME_ENABLED=true` is temporary: the next
scheduled check re-asserts the window's state.

---

### (Manual) Run Once
```bash
source venv/bin/activate
python wifi.py
```

### (Manual) Run the Reset Listener (Telegram `/reset` + downtime)
```bash
source venv/bin/activate
python wifi.py --watch
```
This one process both watches for `/reset` and enforces the downtime schedule.

### (Manual) Run the Test Suite
```bash
PYTHONPATH=. python tests/test_wifi.py
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
