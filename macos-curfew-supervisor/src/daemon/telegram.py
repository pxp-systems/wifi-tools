from __future__ import annotations

import logging
from datetime import datetime

import requests

LOGGER = logging.getLogger(__name__)


class TelegramClient:
    def __init__(self, bot_token: str, chat_ids: list[str]):
        self.bot_token = bot_token
        self.chat_ids = chat_ids

    def enabled(self) -> bool:
        return bool(self.bot_token and self.chat_ids)

    def send(self, text: str) -> None:
        if not self.enabled():
            LOGGER.debug("Telegram disabled; dropping message: %s", text)
            return
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        for chat_id in self.chat_ids:
            try:
                response = requests.post(
                    url,
                    data={"chat_id": chat_id, "text": text},
                    timeout=20,
                )
                if response.status_code != 200:
                    LOGGER.error("Telegram send failed for %s: %s", chat_id, response.text)
            except Exception as exc:
                LOGGER.exception("Telegram exception for %s: %s", chat_id, exc)


def format_event(event: str, username: str | None = None, extra: str | None = None) -> str:
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%SZ")
    parts = [f"[CurfewSupervisor {now}]", event]
    if username:
        parts.append(f"user={username}")
    if extra:
        parts.append(extra)
    return " | ".join(parts)
