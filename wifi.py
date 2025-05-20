from playwright.sync_api import sync_playwright
import random
import string
import requests
import time
from datetime import datetime
import sys
import os

LAST_UPDATE_ID_FILE = "/home/admin/.last_telegram_update"

def send_telegram_message(password):
    token = "7767217949:AAFIYBNDNEV4E7lZpVZSAkl_r2A8CRyQVnc"
    chat_ids = ["7370373994", "1234567890"]
    message = f"🔐 Guest Wi-Fi password for {datetime.now().strftime('%A %d %B')}:\n\n{password}"
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    for chat_id in chat_ids:
        data = {"chat_id": chat_id, "text": message}
        try:
            response = requests.post(url, data=data)
            if response.status_code == 200:
                print(f"✅ Message sent to chat ID {chat_id}")
            else:
                print(f"❌ Failed for chat ID {chat_id}: {response.text}")
        except Exception as e:
            print(f"❌ Telegram error for chat ID {chat_id}:", e)

def generate_password():
    easy_letters = 'asdfgwertcv'
    prefix = ''.join(random.choices(easy_letters, k=3))
    digits = ''.join(random.choices(string.digits, k=5))
    return prefix + digits

def run_browser_automation(new_password):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto("http://192.168.3.1")
            page.wait_for_selector('input[type="password"]', timeout=5000)
            page.fill('input[type="password"]', 'RainbowWookie06')
            page.click('#loginbtn')
            page.wait_for_timeout(2000)

            page.evaluate("""
            () => {
                const items = Array.from(document.querySelectorAll('.nav_item'));
                for (const item of items) {
                    if (item.innerText.trim().includes("More Functions")) {
                        const icon = item.querySelector('div');
                        if (icon) {
                            const rect = icon.getBoundingClientRect();
                            const clickEvent = new MouseEvent('click', {
                                bubbles: true,
                                cancelable: true,
                                clientX: rect.left + rect.width / 2,
                                clientY: rect.top + rect.height / 2
                            });
                            icon.dispatchEvent(clickEvent);
                            break;
                        }
                    }
                }
            }
            """)
            page.wait_for_timeout(2000)

            page.evaluate("""
            () => {
                const guestMenu = document.querySelector('#wlanguest_menuId');
                if (guestMenu) guestMenu.click();
            }
            """)
            page.wait_for_timeout(2000)

            page.fill('input[type="password"]', new_password)
            page.wait_for_timeout(500)
            page.click('text=Save')
            page.wait_for_timeout(2000)
            browser.close()
        return True
    except Exception as e:
        print("❌ Error during password update:", e)
        return False

def run():
    new_password = generate_password()
    success = run_browser_automation(new_password)
    if success:
        send_telegram_message(new_password)

def load_last_update_id():
    if os.path.exists(LAST_UPDATE_ID_FILE):
        with open(LAST_UPDATE_ID_FILE, "r") as f:
            try:
                return int(f.read().strip())
            except:
                return 0
    return 0

def save_last_update_id(update_id):
    with open(LAST_UPDATE_ID_FILE, "w") as f:
        f.write(str(update_id))

def check_for_reset_command():
    token = "7767217949:AAFIYBNDNEV4E7lZpVZSAkl_r2A8CRyQVnc"
    allowed_chat_ids = {"7370373994", "1234567890"}
    base_url = f"https://api.telegram.org/bot{token}/getUpdates"
    last_update_id = load_last_update_id()
    last_reset_time = 0

    print("📡 Bot is now watching for /reset commands...")

    while True:
        try:
            params = {"offset": last_update_id + 1, "timeout": 30}
            response = requests.get(base_url, params=params, timeout=35)
            data = response.json()

            updates = data.get("result", [])
            if updates:
                print(f"🔍 {len(updates)} new update(s) received")

            for update in updates:
                update_id = update["update_id"]
                message = update.get("message", {})
                text = message.get("text", "").strip().lower()
                chat_id = str(message.get("chat", {}).get("id"))

                print(f"📨 Message from {chat_id}: '{text}' (update_id {update_id})")

                if update_id <= last_update_id:
                    print("⚠️ Skipping already processed update.")
                    continue

                if chat_id in allowed_chat_ids and text == "/reset":
                    now = time.time()
                    cooldown_remaining = int(60 - (now - last_reset_time))
                    if now - last_reset_time >= 60:
                        print(f"🔁 Reset triggered at {datetime.now().strftime('%H:%M:%S')}")
                        new_password = generate_password()
                        success = run_browser_automation(new_password)
                        if success:
                            send_telegram_message(new_password)
                            last_reset_time = now
                            print(f"✅ Reset complete and message sent at {datetime.now().strftime('%H:%M:%S')}")
                        else:
                            print(f"❌ Reset failed at {datetime.now().strftime('%H:%M:%S')}")
                    else:
                        print(f"⏳ Reset skipped: {cooldown_remaining}s cooldown remaining")
                else:
                    print("🛑 Ignored: not a valid /reset or unauthorized user")

                last_update_id = update_id
                save_last_update_id(last_update_id)

        except Exception as e:
            print("❌ Telegram polling error:", e)

if __name__ == '__main__':
    if '--watch' in sys.argv:
        check_for_reset_command()
    else:
        run()