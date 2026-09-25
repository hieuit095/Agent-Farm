"""Offline M0 vulnerable/fixed pairs. No network or filesystem writes."""

from pathlib import PurePosixPath
from urllib.parse import urlsplit

RECORDS = {"alice": "alice-private", "bob": "bob-private"}


def authz_vulnerable(actor: str, requested_owner: str) -> str | None:
    return RECORDS.get(requested_owner)


def authz_fixed(actor: str, requested_owner: str) -> str | None:
    return RECORDS.get(requested_owner) if actor == requested_owner else None


def sqli_vulnerable(username: str) -> str:
    return f"SELECT * FROM users WHERE name = '{username}'"


def sqli_fixed(username: str) -> tuple[str, tuple[str]]:
    return "SELECT * FROM users WHERE name = ?", (username,)


def ssrf_vulnerable(url: str) -> bool:
    return bool(urlsplit(url).hostname)


def ssrf_fixed(url: str) -> bool:
    parsed = urlsplit(url)
    return parsed.scheme == "https" and parsed.hostname == "public.example"


def traversal_vulnerable(path: str) -> bool:
    return path.endswith(".txt")


def traversal_fixed(path: str) -> bool:
    parts = PurePosixPath(path).parts
    return path.endswith(".txt") and ".." not in parts and not path.startswith("/")
