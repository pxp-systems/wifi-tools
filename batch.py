from playwright.sync_api import sync_playwright
from wifi_utils import generate_password, send_telegram_message
import os
from dotenv import load_dotenv

load_dotenv()

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

def run():
    new_password = generate_password()
    success = run_browser_automation(new_password)
    if success:
        send_telegram_message(new_password)

if __name__ == '__main__':
    run()
