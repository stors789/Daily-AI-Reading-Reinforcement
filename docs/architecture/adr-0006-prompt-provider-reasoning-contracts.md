# ADR-0006: Visible prompt and capability-aware provider contracts

- Status: Accepted
- Date: 2026-07-16
- Specification: `docs/specs/next-major-release.md`
- Extends: ADR-0003

## Context

DAIRR previously built one article user prompt with Python `str.format`, added a fixed system message in the transport function, and sent a fixed OpenAI-compatible request shape. That design could not show the exact submitted messages, safely validate custom braces and variables, represent plain versus structured output, or express the incompatible reasoning controls used by different providers. Translation review also needs to distinguish reference-free evaluation from comparison against an optional reference without inventing a canonical answer.

## Decision

1. Every model-powered workflow has a stable task identifier and a complete `PromptTemplate` containing the editable system text, editable user text, response mode, visible response contract, version, and documented variables. The initial registry covers article generation, translation review, back-translation review, target-usage validation, segmentation, and preprocessing.
2. Rendering is pure and produces the exact message list used by transport. No host or provider layer may append substantive hidden instructions. Structured mode is rejected unless `{output_format_contract}` occurs visibly in the system or user template. Plain-text mode has no structured parser requirement.
3. Templates use simple named Python-style placeholders. Literal braces use `{{` and `}}`. Attribute/index access, conversions, format specifications, unknown variables, missing referenced values, and unmatched braces are rejected before network I/O. Multiline text is preserved byte-for-character at this layer.
4. Override precedence is profile, then provider, then task default. Import/export uses a versioned plain mapping. Configuration persistence and UI integration remain separate follow-up work.
5. Reasoning configuration represents user intent as `disabled`, `provider_default`, or `explicit`. Explicit control is either a named effort or a token budget, never both. Provider capabilities declare the supported control, dialect, allowed efforts or budget range, and interactions with temperature, top-p, response format, and streaming.
6. Disabled reasoning emits no reasoning/thinking field. Provider default also omits fields unless the capability definition explicitly declares a required default marker. An unknown provider receives conservative no-reasoning capabilities; default/disabled requests remain compatible, while unsupported explicit requests fail validation instead of guessing a field.
7. Provider dialect mapping is isolated in request construction. Initial explicit dialects are OpenAI effort, OpenRouter reasoning effort, Anthropic thinking budget, and Gemini thinking budget. Providers without a verified mapping expose no explicit reasoning control.
8. Advanced request fields cannot override managed fields such as messages, model, sampling, response format, or reasoning. Effective-request diagnostics contain only non-secret settings and safe extra-field names; messages, prompts, credentials, and sensitive advanced values are excluded.
9. Model responses are untrusted. The shared parser accepts explicit plain text or JSON, removes common code fences/envelopes, recovers an object from provider wrapper prose, warns on duplicate fields, accepts useful partial review categories, and reports malformed versus likely truncated output with privacy-safe errors that never embed response content.
10. Whether a reference translation existed is trusted request context. A model response cannot claim a reference was used when none was supplied. Reference-aware prompts describe the reference as an additional comparison point, not the only acceptable translation.

## Consequences

- Prompt preview and transport can share one rendered artifact, eliminating hidden prompt drift.
- Fully custom structured prompts must keep their chosen response contract visible; users can replace the contract itself but cannot hide a mandatory parser contract.
- Existing article `prompt.py` and `llm.py` remain operational until a later integration unit deliberately adapts them to these contracts.
- Provider capability tables are intentionally conservative and require documentation/tests before adding a new dialect or effort value.
- Complete raw prompts may be shown only in an intentional user preview. They must not appear in default logs, exception text, effective-settings diagnostics, or persisted snapshots without an explicit privacy decision.

## Follow-up integration constraints

- Persist prompt presets and reasoning intent through backward-compatible configuration migration; do not place secrets in prompt or effective-request snapshots.
- The UI must label provider-default and disabled distinctly even though both normally omit wire fields.
- Transport adapters must use `RenderedPrompt.messages` unchanged and surface `ProviderConfigurationError` as an actionable, redacted validation error.
- Structured response schemas for article target mappings may extend the generic parser but must retain tolerant fallback and validation at the domain boundary.
