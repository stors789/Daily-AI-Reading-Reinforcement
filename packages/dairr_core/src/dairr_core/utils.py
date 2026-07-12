"""Small platform-agnostic utility functions."""

from __future__ import annotations

import html
import ipaddress
import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from .config import DEFAULT_CONFIG, PROVIDER_PROFILES


def clean_text(value: Any) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def clean_base_url(value: Any) -> str:
    raw = str(value or "").strip().rstrip("/")
    if not raw:
        return ""

    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("API base URL must use HTTPS (or HTTP for a loopback development server).")
    if not parsed.hostname:
        raise ValueError("API base URL must include a host.")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("API base URL must not contain embedded credentials.")
    if parsed.query or parsed.fragment:
        raise ValueError("API base URL must not contain a query string or fragment.")

    if parsed.scheme == "http" and not _is_loopback_host(parsed.hostname):
        raise ValueError("Unencrypted HTTP is only allowed for loopback development servers.")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))


def _is_loopback_host(hostname: str) -> bool:
    if hostname.lower().rstrip(".") == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-")
    return slug[:80] or "deck"


def clamp_word_count(value: int) -> int:
    return max(50, min(10000, int(value)))


def clean_max_words(value: Any) -> str:
    text = clean_text(value)
    if not text:
        return ""
    numbers = [int(match) for match in re.findall(r"\d+", text)]
    if not numbers:
        return ""
    first = clamp_word_count(numbers[0])
    if len(numbers) == 1:
        return str(first)
    second = clamp_word_count(numbers[1])
    low, high = sorted((first, second))
    if low == high:
        return str(high)
    return f"{low}-{high}"


def word_range_bounds(value: Any) -> tuple[int, int] | None:
    cleaned = clean_max_words(value)
    if not cleaned:
        return None
    numbers = [int(match) for match in re.findall(r"\d+", cleaned)]
    if not numbers:
        return None
    if len(numbers) == 1:
        return (numbers[0], numbers[0])
    low, high = sorted((numbers[0], numbers[1]))
    return (low, high)


def card_id_set(value: Any) -> set[int]:
    if not isinstance(value, list):
        return set()
    ids: set[int] = set()
    for item in value:
        try:
            ids.add(int(item))
        except (TypeError, ValueError):
            continue
    return ids


def clean_provider_id(value: Any) -> str:
    provider_id = clean_text(value)
    valid_ids = {profile["id"] for profile in PROVIDER_PROFILES}
    return provider_id if provider_id in valid_ids else "custom"


def clean_temperature(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = float(DEFAULT_CONFIG["temperature"])
    return max(0.0, min(2.0, number))


def clean_max_tokens(value: Any) -> int:
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        number = int(DEFAULT_CONFIG["max_tokens"])
    return max(128, min(32000, number))
