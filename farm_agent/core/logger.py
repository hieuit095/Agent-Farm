"""Daily rotating file logger for Farm-Agent.

Provides a TimedRotatingFileHandler that creates a new log file
at midnight each day. Log files are named `farm_agent_YYYY-MM-DD.log`
and automatically pruned after `keep_days`.

Uses ONLY Python's standard `logging` library — no third-party deps.
"""

from __future__ import annotations

import logging
import re
import sys
from datetime import UTC, datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from farm_agent.core.config import LogConfig

# Patterns that look like API keys / tokens (mask them in logs)
_SECRET_PATTERNS = re.compile(
    r"(ghp_[A-Za-z0-9]{30,})"  # GitHub PAT
    r"|(sk-[A-Za-z0-9]{30,})"  # OpenAI key
    r"|(sk-cp-[A-Za-z0-9_-]{30,})"  # MiniMax streaming API key
    r"|(AIza[A-Za-z0-9_-]{30,})"  # Google API key
    r"|(Bearer\s+[A-Za-z0-9._-]{20,})"  # Bearer tokens
    r"|(\b\d{7,10}:[A-Za-z0-9_-]{35}\b)",  # Telegram Bot Token
    re.IGNORECASE,
)


class _SanitizingFormatter(logging.Formatter):
    """Formatter that masks API keys and tokens in log messages."""

    def format(self, record: logging.LogRecord) -> str:
        original = super().format(record)
        return _SECRET_PATTERNS.sub("****REDACTED****", original)


def setup_daily_logger(config: LogConfig) -> logging.Logger:
    """Configure the root logger with a daily rotating file handler.

    Creates ``logs/farm_agent_YYYY-MM-DD.log`` files that rotate at
    midnight.  Old files are automatically deleted after ``keep_days``.

    Args:
        config: LogConfig with level, log_dir, and keep_days.

    Returns:
        The configured root logger (callers can also use
        ``logging.getLogger(__name__)`` as usual — all messages
        propagate to root).
    """
    log_dir = Path(config.log_dir)

    # Attempt to create the log directory
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        print(
            f"[WARN] Cannot create log directory '{log_dir}': permission denied. "
            "File logging disabled.",
            file=sys.stderr,
        )
        return logging.getLogger()
    except OSError as exc:
        print(
            f"[WARN] Cannot create log directory '{log_dir}': {exc}. File logging disabled.",
            file=sys.stderr,
        )
        return logging.getLogger()

    # Build the log file path: logs/farm_agent_YYYY-MM-DD.log
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    log_file = log_dir / f"farm_agent_{today}.log"

    log_level = getattr(logging, config.level.upper(), logging.INFO)

    # Structured formatter: timestamp | LEVEL    | module | message
    formatter = _SanitizingFormatter(
        fmt="%(asctime)s | %(levelname)-8s | %(module)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # TimedRotatingFileHandler — rotates at midnight, keeps `keep_days` backups
    try:
        handler = TimedRotatingFileHandler(
            filename=str(log_file),
            when="midnight",
            interval=1,
            backupCount=config.keep_days,
            encoding="utf-8",
            utc=True,
        )
        handler.setLevel(log_level)
        handler.setFormatter(formatter)

        # Suffix for rotated files (namer uses the date already in filename)
        handler.suffix = "%Y-%m-%d"

    except PermissionError:
        print(
            f"[WARN] Cannot write to '{log_file}': permission denied. File logging disabled.",
            file=sys.stderr,
        )
        return logging.getLogger()

    # Attach to root logger (does NOT replace existing handlers like RichHandler)
    root = logging.getLogger()
    # Avoid duplicate handlers on repeated calls
    for existing in root.handlers[:]:
        if isinstance(existing, TimedRotatingFileHandler):
            root.removeHandler(existing)
            existing.close()

    root.addHandler(handler)

    # Ensure root logger level is at least as permissive
    if root.level == logging.NOTSET or root.level > log_level:
        root.setLevel(log_level)

    # Silence noisy third-party HTTP loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("github").setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        "Daily rolling logger initialized → %s (level=%s, keep=%d days)",
        log_file,
        config.level,
        config.keep_days,
    )

    return root


def get_today_log_path(log_dir: str = "logs") -> Path | None:
    """Return the path to today's log file, or None if it doesn't exist."""
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    log_file = Path(log_dir) / f"farm_agent_{today}.log"
    return log_file if log_file.exists() else None
