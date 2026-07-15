from __future__ import annotations

import sys
import unittest
from pathlib import Path


CORE_SRC = Path(__file__).resolve().parent.parent / "packages" / "dairr_core" / "src"
if str(CORE_SRC) not in sys.path:
    sys.path.insert(0, str(CORE_SRC))

from dairr_core.provider_capabilities import (
    ProviderCapabilities,
    ProviderConfigurationError,
    ReasoningControl,
    ReasoningDialect,
    ReasoningIntent,
    ReasoningMode,
    known_provider_capabilities,
)
from dairr_core.provider_requests import ChatRequestOptions, build_chat_completion_request


def options(**changes):
    values = {"model": "model-a", "messages": [{"role": "user", "content": "private text"}]}
    values.update(changes)
    return ChatRequestOptions(**values)


class ProviderReasoningTests(unittest.TestCase):
    def test_disabled_and_default_are_distinct_but_both_omit_parameters(self) -> None:
        caps = known_provider_capabilities("openai")
        disabled = build_chat_completion_request(caps, options(), ReasoningIntent(ReasoningMode.DISABLED))
        default = build_chat_completion_request(caps, options(), ReasoningIntent(ReasoningMode.PROVIDER_DEFAULT))
        for built in (disabled, default):
            self.assertNotIn("reasoning_effort", built.body)
            self.assertNotIn("reasoning", built.body)
            self.assertNotIn("thinking", built.body)
            self.assertNotIn("thinking_config", built.body)
        self.assertNotEqual(
            disabled.effective_settings.reasoning_mode,
            default.effective_settings.reasoning_mode,
        )

    def test_inactive_reasoning_cannot_smuggle_explicit_values(self) -> None:
        with self.assertRaises(ProviderConfigurationError) as raised:
            ReasoningIntent(ReasoningMode.DISABLED, effort="minimal")
        self.assertEqual(raised.exception.code, "inactive_reasoning_value")

    def test_openai_explicit_effort_maps_to_named_field(self) -> None:
        intent = ReasoningIntent(ReasoningMode.EXPLICIT, ReasoningControl.EFFORT, effort="low")
        built = build_chat_completion_request(known_provider_capabilities("openai"), options(), intent)
        self.assertEqual(built.body["reasoning_effort"], "low")
        self.assertEqual(built.effective_settings.reasoning_value, "low")

    def test_openrouter_effort_uses_its_dialect(self) -> None:
        intent = ReasoningIntent(ReasoningMode.EXPLICIT, ReasoningControl.EFFORT, effort="high")
        built = build_chat_completion_request(known_provider_capabilities("openrouter"), options(), intent)
        self.assertEqual(built.body["reasoning"], {"effort": "high"})

    def test_anthropic_and_gemini_budget_dialects_are_separate(self) -> None:
        intent = ReasoningIntent(ReasoningMode.EXPLICIT, ReasoningControl.BUDGET, budget_tokens=2048)
        anthropic = build_chat_completion_request(known_provider_capabilities("anthropic"), options(), intent)
        gemini = build_chat_completion_request(known_provider_capabilities("gemini"), options(), intent)
        self.assertEqual(anthropic.body["thinking"], {"type": "enabled", "budget_tokens": 2048})
        self.assertEqual(gemini.body["thinking_config"], {"thinking_budget": 2048})

    def test_effort_and_budget_are_mutually_exclusive(self) -> None:
        with self.assertRaises(ProviderConfigurationError) as raised:
            ReasoningIntent(
                ReasoningMode.EXPLICIT,
                ReasoningControl.EFFORT,
                effort="low",
                budget_tokens=1000,
            )
        self.assertEqual(raised.exception.code, "invalid_effort")

    def test_only_known_efforts_and_valid_budgets_are_accepted(self) -> None:
        invalid_effort = ReasoningIntent(ReasoningMode.EXPLICIT, ReasoningControl.EFFORT, effort="max")
        with self.assertRaises(ProviderConfigurationError) as effort_error:
            build_chat_completion_request(known_provider_capabilities("openai"), options(), invalid_effort)
        self.assertEqual(effort_error.exception.code, "unsupported_effort")

        invalid_budget = ReasoningIntent(ReasoningMode.EXPLICIT, ReasoningControl.BUDGET, budget_tokens=100)
        with self.assertRaises(ProviderConfigurationError) as budget_error:
            build_chat_completion_request(known_provider_capabilities("anthropic"), options(), invalid_budget)
        self.assertEqual(budget_error.exception.code, "budget_too_small")

    def test_unknown_provider_safely_omits_default_and_rejects_explicit(self) -> None:
        caps = known_provider_capabilities("mystery-gateway")
        built = build_chat_completion_request(caps, options(), ReasoningIntent())
        self.assertEqual(set(built.body), {"model", "messages"})
        explicit = ReasoningIntent(ReasoningMode.EXPLICIT, ReasoningControl.EFFORT, effort="low")
        with self.assertRaises(ProviderConfigurationError) as raised:
            build_chat_completion_request(caps, options(), explicit)
        self.assertEqual(raised.exception.code, "unsupported_reasoning")

    def test_provider_default_marker_is_applied_only_when_declared(self) -> None:
        caps = ProviderCapabilities(
            "special",
            ReasoningDialect.OPENAI_EFFORT,
            frozenset({ReasoningControl.EFFORT}),
            ("low",),
            default_reasoning_marker={"reasoning": {"mode": "default"}},
        )
        built = build_chat_completion_request(caps, options(), ReasoningIntent())
        self.assertEqual(built.body["reasoning"], {"mode": "default"})

    def test_reasoning_parameter_conflicts_are_prevented(self) -> None:
        intent = ReasoningIntent(ReasoningMode.EXPLICIT, ReasoningControl.EFFORT, effort="medium")
        with self.assertRaises(ProviderConfigurationError) as temperature:
            build_chat_completion_request(
                known_provider_capabilities("openai"),
                options(temperature=0.0),
                intent,
            )
        self.assertEqual(temperature.exception.code, "reasoning_temperature_conflict")
        with self.assertRaises(ProviderConfigurationError) as top_p:
            build_chat_completion_request(known_provider_capabilities("openai"), options(top_p=0.9), intent)
        self.assertEqual(top_p.exception.code, "reasoning_top_p_conflict")

    def test_zero_temperature_is_preserved_when_allowed(self) -> None:
        built = build_chat_completion_request(
            known_provider_capabilities("openrouter"),
            options(temperature=0.0, top_p=0.0, max_output_tokens=10),
            ReasoningIntent(ReasoningMode.DISABLED),
        )
        self.assertEqual(built.body["temperature"], 0.0)
        self.assertEqual(built.body["top_p"], 0.0)

    def test_unsupported_response_format_and_streaming_are_rejected(self) -> None:
        caps = ProviderCapabilities("limited", supports_response_format=False, supports_streaming=False)
        with self.assertRaises(ProviderConfigurationError) as fmt:
            build_chat_completion_request(caps, options(response_format={"type": "json_object"}))
        self.assertEqual(fmt.exception.code, "unsupported_response_format")
        with self.assertRaises(ProviderConfigurationError) as streaming:
            build_chat_completion_request(caps, options(stream=True))
        self.assertEqual(streaming.exception.code, "unsupported_streaming")

    def test_advanced_body_cannot_override_managed_reasoning_or_messages(self) -> None:
        for field in ("messages", "reasoning", "reasoning_effort", "temperature"):
            with self.subTest(field=field), self.assertRaises(ProviderConfigurationError) as raised:
                build_chat_completion_request(
                    known_provider_capabilities("openrouter"),
                    options(extra_body={field: "override"}),
                )
            self.assertEqual(raised.exception.code, "protected_extra_field")

    def test_effective_settings_are_redacted(self) -> None:
        built = build_chat_completion_request(
            known_provider_capabilities("openrouter"),
            options(extra_body={"seed": 4, "api_token": "secret"}),
        )
        safe = built.effective_settings.to_safe_dict()
        serialized = repr(safe)
        self.assertNotIn("private text", serialized)
        self.assertNotIn("secret", serialized)
        self.assertEqual(safe["extraBodyKeys"], ["seed"])


if __name__ == "__main__":
    unittest.main()
