"""Async notification dispatchers for ContribAI."""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Lightweight, non-blocking asynchronous Telegram dispatcher."""

    def __init__(self, token: str, chat_id: str):
        self.token = token.strip() if token else ""
        self.chat_id = str(chat_id).strip() if chat_id else ""
        self.enabled = bool(self.token and self.chat_id)
        if not self.enabled:
            logger.debug("TelegramNotifier disabled: missing token or chat ID")

    async def send_message(self, text: str) -> None:
        """Send a beautifully formatted message to Telegram.
        
        Guaranteed to never raise an exception that blocks the event loop.
        """
        if not self.enabled:
            return

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                logger.debug("Telegram message sent successfully.")
        except Exception as e:
            logger.warning("Failed to send Telegram notification: %s", e)
