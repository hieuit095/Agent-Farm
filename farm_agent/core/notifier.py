"""Async notification dispatchers for Farm-Agent."""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Lightweight, non-blocking asynchronous Telegram dispatcher.

    Uses a persistent httpx.AsyncClient to avoid connection churn
    and respect Telegram rate limits across long-running sessions.
    """

    def __init__(self, token: str, chat_id: str):
        self.token = token.strip() if token else ""
        self.chat_id = str(chat_id).strip() if chat_id else ""
        self.enabled = bool(self.token and self.chat_id)
        self._last_update_id = 0
        # Persistent HTTP session — reused across all send_message calls
        self._client: httpx.AsyncClient | None = (
            httpx.AsyncClient(timeout=10.0) if self.enabled else None
        )
        if not self.enabled:
            logger.debug("TelegramNotifier disabled: missing token or chat ID")

    async def send_message(self, text: str) -> None:
        """Send a beautifully formatted message to Telegram.

        Guaranteed to never raise an exception that blocks the event loop.
        """
        if not self.enabled or not self._client:
            return

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        try:
            response = await self._client.post(url, json=payload)
            response.raise_for_status()
            logger.debug("Telegram message sent successfully.")
        except Exception as e:
            logger.warning("Failed to send Telegram notification: %s", e)
    async def _register_commands(self) -> None:
        """Register the bot's command menu with Telegram."""
        if not self.enabled or not self._client:
            return

        url = f"https://api.telegram.org/bot{self.token}/setMyCommands"
        payload = {
            "commands": [
                {"command": "status", "description": "Check if the bot is online and running"},
                {"command": "rptoday", "description": "View the PRs generated today"},
                {"command": "quota", "description": "Check Minimax API budget and usage"},
                {"command": "help", "description": "Show the help menu"}
            ]
        }

        try:
            response = await self._client.post(url, json=payload)
            response.raise_for_status()
            logger.debug("Successfully registered Telegram commands menu.")
        except Exception as e:
            logger.warning("Failed to register Telegram commands menu: %s", e)

    async def start_polling(self, memory_instance) -> None:
        """Run long-polling loop to receive Telegram commands."""
        import asyncio
        if not self.enabled or not self._client:
            return

        await self._register_commands()

        logger.info("📡 Bắt đầu lắng nghe lệnh từ Telegram (Long-Polling)...")
        while True:
            try:
                url = f"https://api.telegram.org/bot{self.token}/getUpdates"
                params = {"timeout": 30, "offset": self._last_update_id + 1}
                response = await self._client.get(url, params=params, timeout=40.0)
                response.raise_for_status()
                data = response.json()

                for result in data.get("result", []):
                    self._last_update_id = result["update_id"]
                    
                    message = result.get("message")
                    if not message:
                        continue

                    chat_id = str(message.get("chat", {}).get("id", ""))
                    if chat_id != self.chat_id:
                        logger.warning("Ignoring Telegram command from unauthorized chat: %s", chat_id)
                        continue

                    text = message.get("text", "").strip()
                    if text.startswith("/"):
                        await self._handle_command(text, memory_instance)

            except Exception as e:
                logger.warning("Telegram polling error: %s", e)
                await asyncio.sleep(5)
            
            await asyncio.sleep(1)

    async def _handle_command(self, text: str, memory_instance) -> None:
        """Handle incoming C2 commands from Telegram."""
        import time
        from datetime import UTC, datetime
        
        command = text.split()[0].lower()
        
        if command in ("/start", "/help"):
            msg = (
                "👋 <b>Welcome to Farm-Agent Command Center!</b>\n\n"
                "I am your autonomous GitHub agent. Here is what I can do for you:\n"
                "/status - Check my heartbeat\n"
                "/rptoday - See today's PRs\n"
                "/quota - Check LLM API budget\n\n"
                "Just tap the Menu button or type `/` to start!"
            )
            await self.send_message(msg)
        elif command == "/status":
            await self.send_message("🟢 Bot is online and running.")
        elif command in ("/today", "/rptoday"):
            today_prs_count = await memory_instance.get_today_pr_count()
            
            today_prefix = datetime.now(UTC).date().isoformat()
            recent_prs = await memory_instance.get_prs(limit=50)
            today_urls = [pr["pr_url"] for pr in recent_prs if pr.get("created_at", "").startswith(today_prefix)]
            
            msg = f"📊 <b>Report Today:</b>\nYou have generated {today_prs_count} PRs today."
            if today_urls:
                msg += "\n\n" + "\n".join(today_urls)
            await self.send_message(msg)
        elif command == "/quota":
            now = time.time()
            five_hours_ago = now - 18_000.0
            seven_days_ago = now - 604_800.0
            
            cursor = await memory_instance._db.execute(
                "SELECT COUNT(1) FROM api_usage_log WHERE provider = 'minimax' AND timestamp >= ?",
                (five_hours_ago,)
            )
            row = await cursor.fetchone()
            count_5h = row[0] if row else 0

            cursor = await memory_instance._db.execute(
                "SELECT COUNT(1) FROM api_usage_log WHERE provider = 'minimax' AND timestamp >= ?",
                (seven_days_ago,)
            )
            row = await cursor.fetchone()
            count_7d = row[0] if row else 0
            
            await self.send_message(f"📈 <b>Minimax Quota Usage:</b>\nLast 5h: {count_5h}/1000\nLast 7d: {count_7d}/10000")

    async def close(self) -> None:
        """Release the persistent HTTP connection pool."""
        if self._client:
            await self._client.aclose()
            self._client = None
