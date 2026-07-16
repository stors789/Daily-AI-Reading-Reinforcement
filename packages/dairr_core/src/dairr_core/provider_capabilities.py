"""Provider reasoning capability and user-intent models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping


class ReasoningMode(str, Enum):
    DISABLED = "disabled"
    PROVIDER_DEFAULT = "provider_default"
    EXPLICIT = "explicit"


class ReasoningControl(str, Enum):
    EFFORT = "effort"
    BUDGET = "budget"


class ReasoningDialect(str, Enum):
    NONE = "none"
    OPENAI_EFFORT = "openai_effort"
    OPENROUTER_REASONING = "openrouter_reasoning"
    ANTHROPIC_THINKING = "anthropic_thinking"
    GEMINI_THINKING = "gemini_thinking"


class ProviderConfigurationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class ReasoningIntent:
    mode: ReasoningMode = ReasoningMode.PROVIDER_DEFAULT
    control: ReasoningControl | None = None
    effort: str | None = None
    budget_tokens: int | None = None

    def __post_init__(self) -> None:
        if self.mode is not ReasoningMode.EXPLICIT:
            if self.control is not None or self.effort is not None or self.budget_tokens is not None:
                raise ProviderConfigurationError(
                    "inactive_reasoning_value",
                    "Disabled and provider-default reasoning cannot include explicit values.",
                )
            return
        if self.control is ReasoningControl.EFFORT:
            if not self.effort or self.budget_tokens is not None:
                raise ProviderConfigurationError(
                    "invalid_effort",
                    "Explicit effort requires one named effort and no token budget.",
                )
        elif self.control is ReasoningControl.BUDGET:
            if self.budget_tokens is None or self.effort is not None:
                raise ProviderConfigurationError(
                    "invalid_budget",
                    "Explicit budget requires a token count and no named effort.",
                )
        else:
            raise ProviderConfigurationError(
                "missing_reasoning_control",
                "Explicit reasoning must select effort or budget control.",
            )


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    provider_id: str
    reasoning_dialect: ReasoningDialect = ReasoningDialect.NONE
    reasoning_controls: frozenset[ReasoningControl] = frozenset()
    effort_levels: tuple[str, ...] = ()
    minimum_budget_tokens: int | None = None
    maximum_budget_tokens: int | None = None
    default_reasoning_marker: Mapping[str, Any] | None = None
    supports_temperature_with_reasoning: bool = True
    supports_top_p_with_reasoning: bool = True
    # Native ``response_format`` is not part of the lowest-common-denominator
    # OpenAI-compatible contract.  Unknown/custom endpoints therefore default
    # to textual, prompt-visible response contracts unless a reviewed provider
    # profile explicitly declares support.
    supports_response_format: bool = False
    supports_streaming: bool = True

    @property
    def supports_reasoning(self) -> bool:
        return self.reasoning_dialect is not ReasoningDialect.NONE and bool(self.reasoning_controls)

    def validate_reasoning(self, intent: ReasoningIntent) -> None:
        if intent.mode is not ReasoningMode.EXPLICIT:
            return
        if not self.supports_reasoning or intent.control not in self.reasoning_controls:
            raise ProviderConfigurationError(
                "unsupported_reasoning",
                f"Provider {self.provider_id} does not support the selected reasoning control.",
            )
        if intent.control is ReasoningControl.EFFORT and intent.effort not in self.effort_levels:
            raise ProviderConfigurationError(
                "unsupported_effort",
                f"Unsupported reasoning effort for {self.provider_id}.",
            )
        if intent.control is ReasoningControl.BUDGET:
            budget = int(intent.budget_tokens or 0)
            if self.minimum_budget_tokens is not None and budget < self.minimum_budget_tokens:
                raise ProviderConfigurationError("budget_too_small", "Reasoning budget is below the provider minimum.")
            if self.maximum_budget_tokens is not None and budget > self.maximum_budget_tokens:
                raise ProviderConfigurationError("budget_too_large", "Reasoning budget exceeds the provider maximum.")


def known_provider_capabilities(provider_id: str) -> ProviderCapabilities:
    """Return conservative known capabilities; unknown providers get no guesses."""
    normalized = str(provider_id or "").strip().lower()
    known = {
        "openai": ProviderCapabilities(
            "openai",
            ReasoningDialect.OPENAI_EFFORT,
            frozenset({ReasoningControl.EFFORT}),
            ("minimal", "low", "medium", "high"),
            supports_temperature_with_reasoning=False,
            supports_top_p_with_reasoning=False,
            supports_response_format=True,
        ),
        "openrouter": ProviderCapabilities(
            "openrouter",
            ReasoningDialect.OPENROUTER_REASONING,
            frozenset({ReasoningControl.EFFORT}),
            ("minimal", "low", "medium", "high"),
            supports_response_format=True,
        ),
        "anthropic": ProviderCapabilities(
            "anthropic",
            ReasoningDialect.ANTHROPIC_THINKING,
            frozenset({ReasoningControl.BUDGET}),
            minimum_budget_tokens=1024,
            supports_temperature_with_reasoning=False,
            supports_top_p_with_reasoning=False,
            supports_response_format=True,
        ),
        "gemini": ProviderCapabilities(
            "gemini",
            ReasoningDialect.GEMINI_THINKING,
            frozenset({ReasoningControl.BUDGET}),
            minimum_budget_tokens=0,
            supports_response_format=True,
        ),
        "deepseek": ProviderCapabilities("deepseek"),
        "qwen": ProviderCapabilities("qwen"),
    }
    return known.get(normalized, ProviderCapabilities(normalized or "custom"))
