import sys
import os
from datetime import datetime
from wifi_utils import generate_password, send_telegram_message
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()

ROUTER_PASSWORD = os.getenv("ROUTER_PASSWORD")
ROUTER_URL = os.getenv("ROUTER_URL", "http://192.168.3.1")


def log(msg):
    print(f"[cron_daily_reset {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

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
        log(f"❌ Error during password update: {e}")
        return False

def main():
    log("Starting daily Wi-Fi reset cron job...")
    new_password = generate_password()
    success = run_browser_automation(new_password)
    if success:
        send_telegram_message(new_password)
        log("✅ Wi-Fi password reset and notification sent.")
    else:
        log("❌ Failed to reset Wi-Fi password.")

if __name__ == "__main__":
    main()
