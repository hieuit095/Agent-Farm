"""Async notification dispatchers for Farm-Agent."""

from __future__ import annotations

import logging
from datetime import UTC
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

FAILED_ALERTS_FILE = Path("failed_alerts.log")


async def _persist_failed_alert(message: str, channel: str) -> None:
    """If all notification channels fail, persist alert locally."""
    try:
        with open(FAILED_ALERTS_FILE, "a", encoding="utf-8") as f:
            from datetime import datetime
            timestamp = datetime.now(UTC).isoformat()
            f.write(f"[{timestamp}] [{channel}] PERSISTED ALERT: {message}\n")
    except Exception:
        pass  # last resort — don't fail on this


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
            logger.info("Telegram message delivered successfully.")
        except Exception as e:
            response_text = ""
            if hasattr(e, "response") and e.response is not None:
                response_text = e.response.text[:500]
            elif isinstance(e, httpx.HTTPStatusError):
                response_text = str(e.response.text)[:500]
            logger.error("Failed to deliver Telegram message: %s", response_text or str(e))
            await _persist_failed_alert(text, "telegram")
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
                {"command": "update", "description": "Trigger Alumni Sync — scan new merged PRs"},
                {"command": "clean", "description": "Run Janitor — destroy garbage PRs on GitHub"},
                {"command": "accept", "description": "Hall of Fame — merged PRs (Bảng Vàng)"},
                {"command": "help", "description": "Show the help menu"}
            ]
        }

        try:
            response = await self._client.post(url, json=payload)
            response.raise_for_status()
            logger.debug("Successfully registered Telegram commands menu.")
        except Exception as e:
            logger.error("Failed to register Telegram commands menu: %s", e)

    async def start_polling(self, memory_instance, on_update_callback=None, on_clean_callback=None, on_accept_callback=None) -> None:
        """Run long-polling loop to receive Telegram commands.

        Args:
            memory_instance: The Memory instance for DB queries.
            on_update_callback: Optional async callable — triggers Alumni Sync.
            on_clean_callback: Optional async callable — triggers PR Janitor sweep.
            on_accept_callback: Optional async callable — returns Hall of Fame string.
        """
        import asyncio
        if not self.enabled or not self._client:
            return

        await self._register_commands()

        logger.info("📡 Bắt đầu lắng nghe lệnh từ Telegram (Long-Polling)...")
        delay = 5  # initial backoff in seconds
        max_delay = 60
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
                        await self._handle_command(
                            text,
                            memory_instance,
                            on_update_callback=on_update_callback,
                            on_clean_callback=on_clean_callback,
                            on_accept_callback=on_accept_callback,
                        )

                delay = 5  # reset on success
                await asyncio.sleep(1)  # normal polling interval on success

            except Exception:
                logger.critical("All notification channels failed — persisted to %s", FAILED_ALERTS_FILE)
                await asyncio.sleep(delay)
                delay = min(delay * 2, max_delay)  # double backoff, cap at 60s

    async def _handle_command(self, text: str, memory_instance, on_update_callback=None, on_clean_callback=None, on_accept_callback=None) -> None:
        """Handle incoming C2 commands from Telegram."""
        import time
        from datetime import UTC, datetime

        command = text.strip().split()[0].lower()

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

            today_utc = datetime.now(UTC).date()
            recent_prs = await memory_instance.get_prs(limit=50)
            today_urls = []
            for pr in recent_prs:
                created_str = pr.get("created_at", "")
                if created_str:
                    try:
                        created_dt = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                        if created_dt.tzinfo is None:
                            created_dt = created_dt.replace(tzinfo=UTC)
                        if created_dt.date() == today_utc:
                            today_urls.append(pr["pr_url"])
                    except (ValueError, TypeError):
                        pass  # skip malformed dates

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

        elif command == "/update":
            # Notify user immediately that sync has started
            await self.send_message(
                "⏳ Sếp đợi em một chút nhé, em đang lên GitHub lật lại sổ Nam Tào "
                "xem có khách VIP nào mới gộp PR không..."
            )
            if on_update_callback is not None:
                try:
                    count = await on_update_callback()
                    await self.send_message(
                        f"✅ Báo cáo Sếp! Em đã quét xong. "
                        f"Thêm được {count} khách VIP mới vào danh sách Familiar Grounds ạ!"
                    )
                except Exception as e:
                    await self.send_message(
                        f"❌ Sếp ơi, API GitHub đang dở chứng, "
                        f"đồng bộ thất bại rồi ạ. Lỗi: {e}"
                    )
            else:
                await self.send_message(
                    "⚠️ Alumni Sync callback not configured. Sync is disabled."
                )

        elif command == "/clean":
            # /clean triggers the PR Janitor sweep — destroy garbage PRs via LLM
            await self.send_message(
                "🧹 Sếp đợi em xách chổi lên GitHub quét dọn mấy cái PR rác rưởi nhé..."
            )
            if on_clean_callback is not None:
                try:
                    result = await on_clean_callback()
                    scanned = result.get("total_scanned", 0)
                    destroyed = result.get("garbage_closed", 0)
                    spared = result.get("critical_spared", 0)
                    await self.send_message(
                        f"✨ Dọn xong rồi Sếp ơi! "
                        f"Tổng quét: {scanned}. "
                        f"Đã chém bay màu: {destroyed} rác. "
                        f"Giữ lại: {spared} tinh hoa."
                    )
                except Exception as e:
                    await self.send_message(
                        f"❌ Ây da, cán chổi bị gãy rồi Sếp ơi. Lỗi: {e}"
                    )
            else:
                await self.send_message(
                    "⚠️ Janitor sweep callback not configured. Cleanup is disabled."
                )

        elif command == "/accept":
            # /accept returns the Hall of Fame — merged PRs from the database
            await self.send_message(
                "📜 Sếp đợi em phủi bụi cuốn Sổ Vàng rồi đọc danh sách "
                "chiến tích cho Sếp nghe nhé..."
            )
            if on_accept_callback is not None:
                try:
                    result = await on_accept_callback()
                    await self.send_message(result)
                except Exception as e:
                    await self.send_message(
                        f"❌ Ây da, kẹt tủ rồi Sếp ơi. Lỗi: {e}"
                    )
            else:
                await self.send_message(
                    "⚠️ Hall of Fame callback not configured."
                )

    async def close(self) -> None:
        """Release the persistent HTTP connection pool."""
        if self._client:
            await self._client.aclose()
            self._client = None
