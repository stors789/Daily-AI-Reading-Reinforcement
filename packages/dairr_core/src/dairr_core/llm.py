"""OpenAI-compatible LLM integration with no shell dependency."""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from .config import DEFAULT_CONFIG, PROVIDER_PROFILES, reasoning_intent_from_config
from .prompt import render_article_prompt
from .prompt_templates import RenderedPrompt, ResponseMode
from .provider_capabilities import known_provider_capabilities
from .provider_requests import (
    BuiltProviderRequest,
    ChatRequestOptions,
    EffectiveRequestSettings,
    build_chat_completion_request,
)
from .response_parsing import ParsedModelResponse, ResponseParseError, parse_model_response
from .utils import clean_provider_id, clean_text


class ProviderTransportError(RuntimeError):
    """Privacy-safe provider failure with a stable machine-readable code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.public_message = message


class ProviderRequestCancelled(ProviderTransportError):
    def __init__(self) -> None:
        super().__init__("cancelled", "The AI request was cancelled.")


@dataclass(frozen=True, slots=True)
class ChatCompletionResult:
    content: str
    parsed: ParsedModelResponse
    finish_reason: str
    effective_settings: EffectiveRequestSettings


class OpenAICompatibleTransport:
    """Real transport for the shared practice/article operation services."""

    def __init__(self, config: dict[str, Any], *, timeout: float = 90) -> None:
        self._config = dict(config)
        self._timeout = float(timeout)
        if self._timeout <= 0:
            raise ProviderTransportError("invalid_timeout", "AI request timeout must be positive.")

    def complete(self, request: BuiltProviderRequest, *, cancellation: Any):
        from .operations import ModelResponse

        _raise_if_cancelled(cancellation)
        response_payload = _submit_provider_body(
            self._config,
            request.body,
            timeout=self._timeout,
        )
        _raise_if_cancelled(cancellation)
        content, finish_reason = _chat_content(response_payload)
        return ModelResponse(content, finish_reason)


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
        raise ProviderTransportError("models_http_error", f"Model list request failed with HTTP {exc.code}.") from None
    except urllib.error.URLError as exc:
        detail = _safe_network_detail(exc.reason)
        raise ProviderTransportError("models_network_error", f"Model list request failed: {detail}.") from None

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
    url = f"{base_url.rstrip('/')}/chat/completions"
    data = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": "Reply with OK."}],
        "temperature": 0,
        "max_tokens": 8,
    }).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "DAIRR/config-test",
    }, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise ProviderTransportError("config_test_http_error", f"Configuration test failed with HTTP {exc.code}.") from None
    except urllib.error.URLError as exc:
        detail = _safe_network_detail(exc.reason)
        raise ProviderTransportError("config_test_network_error", f"Configuration test failed: {detail}.") from None
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
    *,
    timeout: float = 90,
    cancelled: Any = None,
) -> str:
    rendered = render_article_prompt(config, deck_name_value, cards, selected_fields, preset)
    return request_chat_completion(
        config,
        rendered,
        timeout=timeout,
        cancelled=cancelled,
    ).content


def request_chat_completion(
    config: dict[str, Any],
    rendered_prompt: RenderedPrompt,
    *,
    timeout: float = 90,
    cancelled: Any = None,
) -> ChatCompletionResult:
    """Submit exactly ``rendered_prompt.messages`` using capability contracts."""
    _raise_if_cancelled(cancelled)
    if timeout <= 0:
        raise ProviderTransportError("invalid_timeout", "AI request timeout must be positive.")
    provider_id = clean_provider_id(config.get("selected_provider_profile"))
    provider = next((p for p in PROVIDER_PROFILES if p["id"] == provider_id), PROVIDER_PROFILES[-1])
    capabilities = known_provider_capabilities(provider_id)
    # Structured prompts always carry their complete, visible textual
    # response contract.  Native ``response_format`` is an optional wire
    # optimization and must not be guessed for custom/unknown endpoints.
    response_format = (
        {"type": "json_object"}
        if rendered_prompt.response_mode is ResponseMode.STRUCTURED
        and capabilities.supports_response_format
        else None
    )
    extra_body = config.get("extra_body") if isinstance(config.get("extra_body"), dict) else {}
    temperature_raw = config.get("temperature", DEFAULT_CONFIG["temperature"])
    temperature = DEFAULT_CONFIG["temperature"] if temperature_raw is None else float(temperature_raw)
    options = ChatRequestOptions(
        model=str(config.get("model") or provider.get("model") or DEFAULT_CONFIG["model"]),
        messages=rendered_prompt.messages,
        max_output_tokens=max_tokens_for_request(config, {}),
        temperature=temperature,
        top_p=float(config["top_p"]) if config.get("top_p") is not None else None,
        response_format=response_format,
        stream=bool(config.get("stream", False)),
        extra_body=extra_body,
    )
    built = build_chat_completion_request(
        capabilities,
        options,
        reasoning_intent_from_config(config.get("reasoning")),
    )
    # The rendered artifact above is the sole source of messages. No transport
    # suffix or hidden system instruction is added here.
    response_payload = _submit_provider_body(config, built.body, timeout=timeout)

    _raise_if_cancelled(cancelled)
    content, finish_reason = _chat_content(response_payload)
    try:
        parsed = parse_model_response(content, rendered_prompt.response_mode, finish_reason=finish_reason)
    except ResponseParseError as exc:
        # Historical custom/default providers may still return the established
        # bracketed article contract. Preserve that valid legacy path while new
        # structured responses remain strictly validated.
        if rendered_prompt.response_mode is ResponseMode.STRUCTURED and "[MAIN_ARTICLE]" in content:
            parsed = parse_model_response(content, ResponseMode.PLAIN_TEXT, finish_reason=finish_reason)
        else:
            raise
    return ChatCompletionResult(content.strip(), parsed, finish_reason, built.effective_settings)


def preview_chat_completion_request(
    config: dict[str, Any],
    rendered_prompt: RenderedPrompt,
) -> dict[str, Any]:
    """Return exact prompt preview plus redacted effective wire settings."""
    provider_id = clean_provider_id(config.get("selected_provider_profile"))
    provider = next((p for p in PROVIDER_PROFILES if p["id"] == provider_id), PROVIDER_PROFILES[-1])
    temperature_raw = config.get("temperature", DEFAULT_CONFIG["temperature"])
    capabilities = known_provider_capabilities(provider_id)
    built = build_chat_completion_request(
        capabilities,
        ChatRequestOptions(
            model=str(config.get("model") or provider.get("model") or DEFAULT_CONFIG["model"]),
            messages=rendered_prompt.messages,
            max_output_tokens=max_tokens_for_request(config, {}),
            temperature=DEFAULT_CONFIG["temperature"] if temperature_raw is None else float(temperature_raw),
            top_p=float(config["top_p"]) if config.get("top_p") is not None else None,
            response_format=(
                {"type": "json_object"}
                if rendered_prompt.response_mode is ResponseMode.STRUCTURED
                and capabilities.supports_response_format
                else None
            ),
            stream=bool(config.get("stream", False)),
            extra_body=config.get("extra_body") if isinstance(config.get("extra_body"), dict) else {},
        ),
        reasoning_intent_from_config(config.get("reasoning")),
    )
    return {"prompt": rendered_prompt.preview(), "effectiveSettings": built.effective_settings.to_safe_dict()}


def _raise_if_cancelled(cancelled: Any) -> None:
    if cancelled is None:
        return
    raise_method = getattr(cancelled, "raise_if_cancelled", None)
    if callable(raise_method):
        raise_method()
        return
    try:
        if callable(cancelled):
            state = cancelled()
        elif hasattr(cancelled, "is_set"):
            state = cancelled.is_set()
        else:
            state = bool(cancelled.cancelled)
    except (AttributeError, TypeError) as exc:
        raise ProviderTransportError("invalid_cancellation_hook", "Cancellation hook is invalid.") from exc
    if state:
        raise ProviderRequestCancelled()


def _submit_provider_body(
    config: dict[str, Any],
    body: dict[str, Any],
    *,
    timeout: float,
) -> Any:
    provider_id = clean_provider_id(config.get("selected_provider_profile"))
    provider = next((p for p in PROVIDER_PROFILES if p["id"] == provider_id), PROVIDER_PROFILES[-1])
    base_url = str(config.get("base_url") or provider.get("base_url") or DEFAULT_CONFIG["base_url"]).rstrip("/")
    if not base_url:
        raise ProviderTransportError("missing_base_url", "An AI provider base URL is required.")
    api_key = str(config.get("api_key") or "").strip()
    if not api_key:
        raise ProviderTransportError("missing_api_key", "An AI provider API key is required.")
    url = f"{base_url}{provider.get('chat_completions_path', '/chat/completions')}"
    try:
        encoded_body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=encoded_body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "DAIRR/provider-transport",
            },
            method="POST",
        )
    except (TypeError, ValueError, UnicodeError):
        raise ProviderTransportError(
            "invalid_provider_request",
            "AI request settings could not be encoded.",
        ) from None
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise ProviderTransportError("http_error", f"AI request failed with HTTP {exc.code}.") from None
    except urllib.error.URLError as exc:
        detail = _safe_network_detail(exc.reason)
        code = "timeout" if detail == "timeout" else "network_error"
        raise ProviderTransportError(code, f"AI request failed: {detail}.") from None
    except (TimeoutError, socket.timeout):
        raise ProviderTransportError("timeout", "AI request timed out.") from None
    except (UnicodeError, json.JSONDecodeError):
        raise ProviderTransportError("malformed_provider_json", "AI provider returned malformed JSON.") from None
    except (ValueError, TypeError):
        raise ProviderTransportError("invalid_provider_url", "AI provider URL is invalid.") from None


def _chat_content(response_payload: Any) -> tuple[str, str]:
    try:
        choice = response_payload["choices"][0]
        content = choice["message"]["content"]
        finish_reason = str(choice.get("finish_reason") or "")
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderTransportError(
            "invalid_chat_completion",
            "AI response did not contain a chat completion message.",
        ) from exc
    if not isinstance(content, str):
        raise ProviderTransportError("invalid_chat_completion", "AI response did not contain text content.")
    return content, finish_reason


def _safe_network_detail(reason: Any) -> str:
    """Map network failures to a small allow-list; never echo URLs or bodies."""
    if isinstance(reason, (TimeoutError, socket.timeout)):
        return "timeout"
    lowered = str(reason or "").lower()
    if "timed out" in lowered or "timeout" in lowered:
        return "timeout"
    if "refused" in lowered:
        return "connection refused"
    if "certificate" in lowered or "ssl" in lowered:
        return "TLS verification failed"
    if "name or service" in lowered or "nodename" in lowered or "dns" in lowered:
        return "DNS lookup failed"
    return "provider unreachable"
