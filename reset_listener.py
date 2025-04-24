import time
from datetime import datetime
import requests
import os
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from wifi_utils import generate_password, send_telegram_message

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_CHAT_IDS = set(os.getenv("TELEGRAM_CHAT_IDS", "").split(","))
ROUTER_PASSWORD = os.getenv("ROUTER_PASSWORD")
ROUTER_URL = os.getenv("ROUTER_URL", "http://192.168.3.1")


def run_browser_automation(new_password):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(ROUTER_URL)
            page.wait_for_selector('input[type="password"]', timeout=5000)
            page.fill('input[type="password"]', ROUTER_PASSWORD)
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

def check_for_reset_command():
    token = TELEGRAM_BOT_TOKEN
    allowed_chat_ids = ALLOWED_CHAT_IDS
    base_url = f"https://api.telegram.org/bot{token}/getUpdates"
    last_update_id = 0
    last_reset_time = 0

    while True:
        try:
            params = {"offset": last_update_id + 1, "timeout": 30}
            response = requests.get(base_url, params=params, timeout=35)
            data = response.json()

            updates = data.get("result", [])
            if updates:
                print(f"🔍 Found {len(updates)} update(s)")
            for update in updates:
                update_id = update["update_id"]
                message = update.get("message", {})
                text = message.get("text", "").strip().lower()
                chat_id = str(message.get("chat", {}).get("id"))

                if chat_id in allowed_chat_ids and text == "/reset":
                    now = time.time()
                    if now - last_reset_time >= 60:
                        print(f"🔁 Reset triggered at {datetime.now().strftime('%H:%M:%S')}")
                        new_password = generate_password()
                        success = run_browser_automation(new_password)
                        if success:
                            send_telegram_message(new_password)
                            last_reset_time = now
                    else:
                        print(f"⏳ Ignored duplicate reset at {datetime.now().strftime('%H:%M:%S')}, last was {int(now - last_reset_time)}s ago")

            if updates:
                last_update_id = updates[-1]["update_id"]

        except Exception as e:
            print("❌ Telegram polling error:", e)

if __name__ == '__main__':
    check_for_reset_command()
