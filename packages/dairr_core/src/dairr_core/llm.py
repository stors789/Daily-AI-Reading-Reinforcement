"""OpenAI-compatible LLM integration with no shell dependency."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from .config import DEFAULT_CONFIG, PROVIDER_PROFILES
from .prompt import build_prompt
from .utils import clean_base_url, clean_provider_id, clean_text


def _authorized_request(url: str, api_key: str, **kwargs: Any) -> urllib.request.Request:
    """Build a request whose credential is not copied by urllib redirects."""
    headers = dict(kwargs.pop("headers", {}))
    request = urllib.request.Request(url, headers=headers, **kwargs)
    request.add_unredirected_header("Authorization", f"Bearer {api_key}")
    return request


def _network_error(operation: str, exc: BaseException) -> RuntimeError:
    if isinstance(exc, urllib.error.HTTPError):
        return RuntimeError(f"{operation} failed with HTTP {exc.code}.")
    return RuntimeError(f"{operation} failed because the server could not be reached.")


def max_tokens_for_request(config: dict[str, Any], preset: dict[str, str]) -> int:
    return int(config.get("max_tokens") or DEFAULT_CONFIG["max_tokens"])


def fetch_openai_compatible_models(base_url: str, api_key: str) -> list[str]:
    url = f"{clean_base_url(base_url)}/models"
    request = _authorized_request(
        url,
        api_key,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise _network_error("Model list request", exc) from exc
    except urllib.error.URLError as exc:
        raise _network_error("Model list request", exc) from exc

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


def test_openai_compatible_config(base_url: str, api_key: str, model: str) -> dict[str, Any]:
    """Make a tiny real chat request to verify endpoint, credentials and model."""
    url = f"{clean_base_url(base_url)}/chat/completions"
    data = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": "Reply with OK."}],
        "temperature": 0,
        "max_tokens": 8,
    }).encode("utf-8")
    request = _authorized_request(url, api_key, data=data, headers={
        "Content-Type": "application/json",
        "User-Agent": "DAIRR/config-test",
    }, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise _network_error("Configuration test", exc) from exc
    except urllib.error.URLError as exc:
        raise _network_error("Configuration test", exc) from exc
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("Configuration test returned an invalid chat completion response.") from exc
    return {"model": model, "response": str(content).strip()[:120]}


def generate_article(
    config: dict[str, Any],
    deck_name_value: str,
    cards: list[Any],
    selected_fields: list[str],
    preset: dict[str, str],
) -> str:
    provider_id = clean_provider_id(config.get("selected_provider_profile"))
    provider = next((p for p in PROVIDER_PROFILES if p["id"] == provider_id), PROVIDER_PROFILES[-1])
    base_url = clean_base_url(config.get("base_url") or provider.get("base_url") or DEFAULT_CONFIG["base_url"])
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
    request = _authorized_request(
        url,
        str(config["api_key"]),
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise _network_error("AI request", exc) from exc
    except urllib.error.URLError as exc:
        raise _network_error("AI request", exc) from exc

    try:
        return response_payload["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("AI response did not contain a chat completion message.") from exc
