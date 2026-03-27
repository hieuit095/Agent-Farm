"""Daily Markdown Logger for Super Human Mode.

Generates a human-readable `daily_log/daily_log_YYYY-MM-DD.md` file
that builds a timestamped timeline of the agent's daily achievements.

Designed for edge deployments where terminal monitoring is impractical.
All writes are non-blocking — file I/O failures are logged but never
crash the SuperHumanLoop.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Default directory relative to the process working directory
_DEFAULT_DIR = "daily_log"


class DailyMarkdownLogger:
    """Append-only daily markdown log writer.

    Creates one file per calendar day with timestamped milestone entries.
    Thread-safe by design: each ``log()`` call opens, appends, and closes
    the file immediately — no long-lived file handles.
    """

    def __init__(self, log_dir: str | Path = _DEFAULT_DIR) -> None:
        self._log_dir = Path(log_dir)
        self._today: str | None = None

    # ── Public API ────────────────────────────────────────────────────

    def log_new_day(self, daily_limit: int) -> None:
        """Log the start of a new day with the PR target."""
        self._write(f"🎯 NEW DAY: Daily target set to {daily_limit} successful PRs.")

    def log_hunt_success(
        self, repo: str, pr_number: int, pr_url: str,
    ) -> None:
        """Log a successful PR creation from a Hunt action."""
        self._write(
            f"🦅 HUNT: Created PR #{pr_number} on `{repo}` "
            f"([link]({pr_url}))."
        )

    def log_hunt_no_result(self, repos_analyzed: int) -> None:
        """Log a Hunt that analyzed repos but created no PRs."""
        self._write(
            f"🦅 HUNT: Analyzed {repos_analyzed} repo(s), no PR created."
        )

    def log_patrol_result(
        self,
        prs_checked: int,
        fixes_pushed: int,
        replies_sent: int,
        ci_fixes: int = 0,
    ) -> None:
        """Log the outcome of a Patrol sweep."""
        parts = [f"Checked {prs_checked} PR(s)"]
        if fixes_pushed:
            parts.append(f"{fixes_pushed} fix(es) pushed")
        if replies_sent:
            parts.append(f"{replies_sent} reply(ies) sent")
        if ci_fixes:
            parts.append(f"{ci_fixes} CI fix(es)")
        self._write(f"🛡️ PATROL: {', '.join(parts)}.")

    def log_patrol_empty(self) -> None:
        """Log when Patrol finds no open PRs to check."""
        self._write("🛡️ PATROL: No open PRs to check.")

    def log_quota_met(self, today_prs: int, daily_limit: int) -> None:
        """Log the moment the daily quota is reached."""
        self._write(
            f"🛑 QUOTA MET: {today_prs}/{daily_limit} PRs created. "
            f"Switched to Patrol-only mode."
        )

    def log_error(self, action: str, error: str) -> None:
        """Log an error that triggered a stress break."""
        self._write(f"⚠️ ERROR during {action}: {error[:200]}")

    def log_shutdown(self, iterations: int) -> None:
        """Log a clean shutdown (time-warp exit or Ctrl+C)."""
        self._write(
            f"🏁 SHUTDOWN: Completed {iterations} iteration(s). Goodbye."
        )

    # ── Internals ─────────────────────────────────────────────────────

    def _write(self, message: str) -> None:
        """Append a timestamped entry to today's daily log file.

        Non-blocking: any I/O error is logged to the terminal logger
        but never raised to the caller.
        """
        try:
            now = datetime.now()
            date_str = now.strftime("%Y-%m-%d")
            time_str = now.strftime("%H:%M")

            os.makedirs(self._log_dir, exist_ok=True)
            filepath = self._log_dir / f"daily_log_{date_str}.md"

            # Create header on first write of the day
            is_new = not filepath.exists()

            with open(filepath, "a", encoding="utf-8") as f:
                if is_new:
                    f.write(f"# 🤖 Super Human Log: {date_str}\n\n")
                f.write(f"- **[{time_str}]** {message}\n")

            self._today = date_str

        except Exception as exc:
            logger.error(
                "DailyMarkdownLogger: failed to write log entry: %s", exc,
            )
