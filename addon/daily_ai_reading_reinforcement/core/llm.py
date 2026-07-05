# LLM API integration, extracted from __init__.py.
# These do not depend on Anki/aqt/mw/gui_hooks.

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from .config import DEFAULT_CONFIG, PROVIDER_PROFILES
from .prompt import build_prompt
from .utils import clean_provider_id, clean_text


def max_tokens_for_request(config: dict[str, Any], preset: dict[str, str]) -> int:
    return int(config.get("max_tokens") or DEFAULT_CONFIG["max_tokens"])


def fetch_openai_compatible_models(base_url: str, api_key: str) -> list[str]:
    url = f"{base_url.rstrip('/')}/models"
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Model list request failed with HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Model list request failed: {exc.reason}") from exc

    raw_models = response_payload.get("data") if isinstance(response_payload, dict) else response_payload
    models: list[str] = []
    if isinstance(raw_models, list):
        for item in raw_models:
            if isinstance(item, dict):
                model_id = clean_text(item.get("id"))
            else:
                model_id = clean_text(item)
            if model_id:
                models.append(model_id)
    return sorted(set(models), key=str.lower)


def generate_article(
    config: dict[str, Any],
    deck_name_value: str,
    cards: list[Any],
    selected_fields: list[str],
    preset: dict[str, str],
) -> str:
    provider_id = clean_provider_id(config.get("selected_provider_profile"))
    provider = next((p for p in PROVIDER_PROFILES if p["id"] == provider_id), PROVIDER_PROFILES[-1])
    base_url = str(config.get("base_url") or provider.get("base_url") or DEFAULT_CONFIG["base_url"]).rstrip("/")
    chat_path = provider.get("chat_completions_path", "/chat/completions")
    url = f"{base_url}{chat_path}"
    prompt = build_prompt(config, deck_name_value, cards, selected_fields, preset)
    request_payload = {
        "model": config.get("model") or provider.get("model") or DEFAULT_CONFIG["model"],
        "messages": [
            {
                "role": "system",
                "content": "Follow the requested output format and language boundaries exactly.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": float(config.get("temperature") or DEFAULT_CONFIG["temperature"]),
        "max_tokens": max_tokens_for_request(config, preset),
    }
    data = json.dumps(request_payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"AI request failed with HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"AI request failed: {exc.reason}") from exc

    try:
        return response_payload["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("AI response did not contain a chat completion message.") from exc
