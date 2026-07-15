"""Capability-aware, redacted OpenAI-compatible request construction."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .provider_capabilities import (
    ProviderCapabilities,
    ProviderConfigurationError,
    ReasoningControl,
    ReasoningDialect,
    ReasoningIntent,
    ReasoningMode,
)


_PROTECTED_FIELDS = {
    "model", "messages", "temperature", "top_p", "max_tokens",
    "max_completion_tokens", "response_format", "stream", "reasoning_effort",
    "reasoning", "thinking", "thinking_config",
}
_SENSITIVE_KEY_PARTS = ("key", "token", "secret", "authorization", "password", "prompt", "message", "content")


@dataclass(frozen=True, slots=True)
class ChatRequestOptions:
    model: str
    messages: Sequence[Mapping[str, str]]
    max_output_tokens: int | None = None
    temperature: float | None = None
    top_p: float | None = None
    response_format: Mapping[str, Any] | None = None
    stream: bool = False
    extra_body: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class EffectiveRequestSettings:
    provider_id: str
    model: str
    reasoning_mode: ReasoningMode
    reasoning_control: ReasoningControl | None
    reasoning_value: str | int | None
    temperature: float | None
    top_p: float | None
    max_output_tokens: int | None
    response_format_enabled: bool
    streaming: bool
    extra_body_keys: tuple[str, ...]

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "providerId": self.provider_id,
            "model": self.model,
            "reasoningMode": self.reasoning_mode.value,
            "reasoningControl": self.reasoning_control.value if self.reasoning_control else None,
            "reasoningValue": self.reasoning_value,
            "temperature": self.temperature,
            "topP": self.top_p,
            "maxOutputTokens": self.max_output_tokens,
            "responseFormatEnabled": self.response_format_enabled,
            "streaming": self.streaming,
            "extraBodyKeys": list(self.extra_body_keys),
        }


@dataclass(frozen=True, slots=True)
class BuiltProviderRequest:
    body: dict[str, Any]
    effective_settings: EffectiveRequestSettings


def build_chat_completion_request(
    capabilities: ProviderCapabilities,
    options: ChatRequestOptions,
    reasoning: ReasoningIntent | None = None,
) -> BuiltProviderRequest:
    reasoning = reasoning or ReasoningIntent()
    capabilities.validate_reasoning(reasoning)
    _validate_options(capabilities, options, reasoning)
    body: dict[str, Any] = {
        "model": options.model,
        "messages": [dict(message) for message in options.messages],
    }
    if options.max_output_tokens is not None:
        body["max_tokens"] = options.max_output_tokens
    if options.temperature is not None:
        body["temperature"] = options.temperature
    if options.top_p is not None:
        body["top_p"] = options.top_p
    if options.response_format is not None:
        body["response_format"] = deepcopy(dict(options.response_format))
    if options.stream:
        body["stream"] = True

    extra = deepcopy(dict(options.extra_body))
    collisions = sorted(_PROTECTED_FIELDS.intersection(extra))
    if collisions:
        raise ProviderConfigurationError(
            "protected_extra_field",
            "Advanced request fields cannot override managed fields: " + ", ".join(collisions),
        )
    body.update(extra)
    _apply_reasoning(body, capabilities, reasoning)

    value: str | int | None = None
    if reasoning.mode is ReasoningMode.EXPLICIT:
        value = reasoning.effort if reasoning.control is ReasoningControl.EFFORT else reasoning.budget_tokens
    effective = EffectiveRequestSettings(
        provider_id=capabilities.provider_id,
        model=options.model,
        reasoning_mode=reasoning.mode,
        reasoning_control=reasoning.control,
        reasoning_value=value,
        temperature=options.temperature,
        top_p=options.top_p,
        max_output_tokens=options.max_output_tokens,
        response_format_enabled=options.response_format is not None,
        streaming=options.stream,
        extra_body_keys=tuple(sorted(key for key in extra if not _sensitive_key(key))),
    )
    return BuiltProviderRequest(body, effective)


def _validate_options(
    capabilities: ProviderCapabilities,
    options: ChatRequestOptions,
    reasoning: ReasoningIntent,
) -> None:
    if not options.model.strip():
        raise ProviderConfigurationError("missing_model", "A model name is required.")
    if not options.messages:
        raise ProviderConfigurationError("missing_messages", "At least one rendered prompt message is required.")
    if options.max_output_tokens is not None and options.max_output_tokens < 1:
        raise ProviderConfigurationError("invalid_max_tokens", "Maximum output tokens must be positive.")
    for name, value in (("temperature", options.temperature), ("top_p", options.top_p)):
        if value is not None and not 0 <= value <= (2 if name == "temperature" else 1):
            raise ProviderConfigurationError(f"invalid_{name}", f"{name} is outside the supported range.")
    active = reasoning.mode is ReasoningMode.EXPLICIT
    if active and options.temperature is not None and not capabilities.supports_temperature_with_reasoning:
        raise ProviderConfigurationError(
            "reasoning_temperature_conflict",
            f"Provider {capabilities.provider_id} does not support temperature with explicit reasoning.",
        )
    if active and options.top_p is not None and not capabilities.supports_top_p_with_reasoning:
        raise ProviderConfigurationError(
            "reasoning_top_p_conflict",
            f"Provider {capabilities.provider_id} does not support top-p with explicit reasoning.",
        )
    if options.response_format is not None and not capabilities.supports_response_format:
        raise ProviderConfigurationError("unsupported_response_format", "Provider does not support response_format.")
    if options.stream and not capabilities.supports_streaming:
        raise ProviderConfigurationError("unsupported_streaming", "Provider does not support streaming.")


def _apply_reasoning(
    body: dict[str, Any],
    capabilities: ProviderCapabilities,
    reasoning: ReasoningIntent,
) -> None:
    if reasoning.mode is ReasoningMode.DISABLED:
        return
    if reasoning.mode is ReasoningMode.PROVIDER_DEFAULT:
        if capabilities.default_reasoning_marker:
            for key, value in capabilities.default_reasoning_marker.items():
                if key in _PROTECTED_FIELDS and key in body:
                    raise ProviderConfigurationError(
                        "default_marker_collision",
                        "Provider default marker conflicts with request fields.",
                    )
                body[str(key)] = deepcopy(value)
        return
    if capabilities.reasoning_dialect is ReasoningDialect.OPENAI_EFFORT:
        body["reasoning_effort"] = reasoning.effort
    elif capabilities.reasoning_dialect is ReasoningDialect.OPENROUTER_REASONING:
        body["reasoning"] = {"effort": reasoning.effort}
    elif capabilities.reasoning_dialect is ReasoningDialect.ANTHROPIC_THINKING:
        body["thinking"] = {"type": "enabled", "budget_tokens": reasoning.budget_tokens}
    elif capabilities.reasoning_dialect is ReasoningDialect.GEMINI_THINKING:
        body["thinking_config"] = {"thinking_budget": reasoning.budget_tokens}
    else:
        raise ProviderConfigurationError("unsupported_reasoning", "Provider reasoning dialect is unsupported.")


def _sensitive_key(key: str) -> bool:
    lowered = str(key).lower()
    return any(part in lowered for part in _SENSITIVE_KEY_PARTS)
