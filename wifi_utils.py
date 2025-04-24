import os
import random
import string
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_IDS = os.getenv("TELEGRAM_CHAT_IDS", "").split(",")
ROUTER_PASSWORD = os.getenv("ROUTER_PASSWORD")
ROUTER_URL = os.getenv("ROUTER_URL", "http://192.168.3.1")

def send_telegram_message(password):
    token = TELEGRAM_BOT_TOKEN
    chat_ids = TELEGRAM_CHAT_IDS
    message = f"🔐 Guest Wi-Fi password for {datetime.now().strftime('%A %d %B')}:\n\n{password}"
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    for chat_id in chat_ids:
        data = {"chat_id": chat_id.strip(), "text": message}
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
