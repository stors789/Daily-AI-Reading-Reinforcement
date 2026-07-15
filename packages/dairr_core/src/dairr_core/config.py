"""Platform-agnostic configuration defaults and non-destructive migration.

Configuration is intentionally represented as plain mappings because both the
Anki add-on and standalone hosts already persist JSON-shaped dictionaries.
Known release fields are validated here while unknown and host-local fields
are retained verbatim for forward compatibility.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


CONFIG_SCHEMA_VERSION = 2
PROMPT_CONFIG_SCHEMA_VERSION = 1

PROVIDER_PROFILES = [
    {
        "id": "openai",
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "chat_completions_path": "/chat/completions",
        "default_model": "gpt-4o-mini",
        "model": "gpt-4o-mini",
        "docs_url": "https://platform.openai.com/docs/api-reference/chat",
        "verified_at": "2026-07-01",
        "auth_notes": "Bearer token with sk-...",
        "compatibility_notes": "Official OpenAI API.",
    },
    {
        "id": "deepseek",
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com",
        "chat_completions_path": "/chat/completions",
        "default_model": "deepseek-v4-flash",
        "model": "deepseek-v4-flash",
        "docs_url": "https://platform.deepseek.com/api-docs/",
        "verified_at": "2026-07-01",
        "auth_notes": "Bearer token.",
        "compatibility_notes": "OpenAI-compatible chat completions. Legacy deepseek-chat is documented as deprecated on 2026-07-24.",
    },
    {
        "id": "qwen",
        "name": "Qwen DashScope",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "chat_completions_path": "/chat/completions",
        "default_model": "qwen-plus",
        "model": "qwen-plus",
        "docs_url": "https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope",
        "verified_at": "2026-07-01",
        "auth_notes": "Bearer token from DashScope console.",
        "compatibility_notes": "OpenAI-compatible chat completions. Official docs recommend workspace-specific regional base URLs where available; the legacy dashscope.aliyuncs.com endpoint remains usable.",
    },
    {
        "id": "openrouter",
        "name": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "chat_completions_path": "/chat/completions",
        "default_model": "openai/gpt-4o-mini",
        "model": "openai/gpt-4o-mini",
        "docs_url": "https://openrouter.ai/docs/api-reference/chat-completion",
        "verified_at": "2026-07-01",
        "auth_notes": "Bearer token.",
        "compatibility_notes": "OpenAI-compatible chat completions through /api/v1/chat/completions.",
    },
    {
        "id": "custom",
        "name": "Custom compatible API",
        "base_url": "",
        "chat_completions_path": "/chat/completions",
        "default_model": "",
        "model": "",
        "docs_url": "",
        "verified_at": "",
        "auth_notes": "Provide appropriate credentials.",
        "compatibility_notes": "Assumes standard OpenAI chat completions endpoint (/chat/completions).",
    },
]


DEFAULT_CONFIG = {
    "config_schema_version": CONFIG_SCHEMA_VERSION,
    "api_key": "",
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-4.1-mini",
    "selected_provider_profile": "openai",
    "llm_api_profiles": [],
    "selected_llm_api_profile_id": "",
    "temperature": 0.7,
    "max_tokens": 30000,
    "prompt_template": "",
    "deck_field_config": {},
    "create_article_cards": False,
    "last_selected_deck_id": "",
    "collapsed_deck_groups": [],
    "ui_language": "zh",
    "ui_theme": "light",
    "momo_api_key": "",
    "momo_day_start": "04:00",
    "momo_day_end": "04:00",
    "prompt_presets": [
        {
            "id": "default",
            "name": "Default",
            "reader_native_language": "",
            "article_language": "",
            "difficulty": "",
            "max_words": "",
            "instructions": "",
            "prompt_template": "",
        }
    ],
    "selected_prompt_preset_id": "default",
    "ai_prompt_config": {
        "schema_version": PROMPT_CONFIG_SCHEMA_VERSION,
        "task_overrides": {},
        "provider_overrides": {},
        "profile_overrides": {},
    },
    "reasoning": {"mode": "provider_default"},
    # Filled with the recommended preset by normalize_config(). Keeping the
    # literal default dependency-free preserves legacy direct-file imports.
    "scoring_presets": [],
    "selected_scoring_preset_id": "recommended-v1",
}


class ConfigValidationError(ValueError):
    """A user-correctable config error that never contains secret values."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def normalize_config(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    """Migrate and validate config without discarding unknown/local fields.

    Corrupt optional release fields fall back independently, keeping an old
    profile or config usable. A future top-level schema is retained rather than
    destructively rewritten; callers can still read compatible legacy fields.
    """
    source = deepcopy(dict(raw)) if isinstance(raw, Mapping) else {}
    result = deepcopy(DEFAULT_CONFIG)
    result.update(source)
    version = _safe_int(source.get("config_schema_version"), 1, minimum=1)
    result["config_schema_version"] = max(version, CONFIG_SCHEMA_VERSION)
    result["temperature"] = _safe_float(source.get("temperature"), DEFAULT_CONFIG["temperature"], 0, 2)
    result["max_tokens"] = _safe_int(source.get("max_tokens"), DEFAULT_CONFIG["max_tokens"], minimum=1)
    result["llm_api_profiles"] = normalize_llm_api_profiles(result)
    result["ai_prompt_config"] = normalize_prompt_config(source.get("ai_prompt_config"))
    reasoning_source = source.get("reasoning") if isinstance(source.get("reasoning"), Mapping) else {}
    reasoning_payload = deepcopy(dict(reasoning_source))
    for key in ("mode", "control", "effort", "budget_tokens"):
        reasoning_payload.pop(key, None)
    reasoning_payload.update(reasoning_intent_to_dict(reasoning_intent_from_config(reasoning_source)))
    result["reasoning"] = reasoning_payload
    result["scoring_presets"] = _normalize_scoring_presets(source.get("scoring_presets"))
    selected = str(source.get("selected_scoring_preset_id") or "").strip()
    valid_ids = {item["id"] for item in result["scoring_presets"]}
    result["selected_scoring_preset_id"] = selected if selected in valid_ids else result["scoring_presets"][0]["id"]
    return result


def normalize_prompt_config(raw: Any) -> dict[str, Any]:
    source = deepcopy(dict(raw)) if isinstance(raw, Mapping) else {}
    result = dict(source)
    result["schema_version"] = PROMPT_CONFIG_SCHEMA_VERSION
    for key in ("task_overrides", "provider_overrides", "profile_overrides"):
        value = source.get(key)
        result[key] = deepcopy(dict(value)) if isinstance(value, Mapping) else {}
    return result


def prompt_registry_from_config(config: Mapping[str, Any]) -> PromptRegistry:
    """Build the effective registry, ignoring only individually invalid presets."""
    from .prompt_templates import default_prompt_registry

    registry = default_prompt_registry()
    stored = normalize_prompt_config(config.get("ai_prompt_config"))
    for task_name, payload in stored["task_overrides"].items():
        _register_prompt_payload(registry, task_name, payload)
    for provider_id, tasks in stored["provider_overrides"].items():
        if isinstance(tasks, Mapping):
            for task_name, payload in tasks.items():
                _register_prompt_payload(registry, task_name, payload, provider_id=str(provider_id))
    for profile_id, tasks in stored["profile_overrides"].items():
        if isinstance(tasks, Mapping):
            for task_name, payload in tasks.items():
                _register_prompt_payload(registry, task_name, payload, profile_id=str(profile_id))
    return registry


def export_prompt_registry_overrides(registry: PromptRegistry, *, existing: Any = None) -> dict[str, Any]:
    """Serialize overrides while retaining unknown extension fields."""
    from .prompt_templates import default_prompt_registry

    result = normalize_prompt_config(existing)
    task_overrides = deepcopy(dict(result.get("task_overrides") or {}))
    for task, template in registry.defaults.items():
        if template != default_prompt_registry().defaults.get(task):
            task_overrides[task.value] = _merge_known(task_overrides.get(task.value), template.to_dict())
    result["task_overrides"] = task_overrides
    providers: dict[str, dict[str, Any]] = deepcopy(dict(result.get("provider_overrides") or {}))
    for (task, provider_id), template in registry.provider_overrides.items():
        current = providers.setdefault(provider_id, {}).get(task.value)
        providers[provider_id][task.value] = _merge_known(current, template.to_dict())
    profiles: dict[str, dict[str, Any]] = deepcopy(dict(result.get("profile_overrides") or {}))
    for (task, profile_id), template in registry.profile_overrides.items():
        current = profiles.setdefault(profile_id, {}).get(task.value)
        profiles[profile_id][task.value] = _merge_known(current, template.to_dict())
    result["provider_overrides"] = providers
    result["profile_overrides"] = profiles
    return result


def reasoning_intent_from_config(raw: Any) -> ReasoningIntent:
    from .provider_capabilities import (
        ProviderConfigurationError,
        ReasoningControl,
        ReasoningIntent,
        ReasoningMode,
    )

    payload = dict(raw) if isinstance(raw, Mapping) else {}
    try:
        mode = ReasoningMode(str(payload.get("mode") or "provider_default"))
        control_raw = payload.get("control")
        control = ReasoningControl(str(control_raw)) if control_raw else None
        effort = str(payload["effort"]) if payload.get("effort") is not None else None
        budget = int(payload["budget_tokens"]) if payload.get("budget_tokens") is not None else None
        return ReasoningIntent(mode, control, effort, budget)
    except (ValueError, TypeError, ProviderConfigurationError):
        return ReasoningIntent(ReasoningMode.PROVIDER_DEFAULT)


def reasoning_intent_to_dict(intent: ReasoningIntent) -> dict[str, Any]:
    from .provider_capabilities import ReasoningControl, ReasoningMode

    result: dict[str, Any] = {"mode": intent.mode.value}
    if intent.mode is ReasoningMode.EXPLICIT:
        result["control"] = intent.control.value if intent.control else None
        if intent.control is ReasoningControl.EFFORT:
            result["effort"] = intent.effort
        else:
            result["budget_tokens"] = intent.budget_tokens
    return result


def _register_prompt_payload(
    registry: PromptRegistry,
    task_name: Any,
    payload: Any,
    *,
    provider_id: str = "",
    profile_id: str = "",
) -> None:
    from .prompt_templates import PromptTask, PromptTemplate, PromptTemplateError

    try:
        task = PromptTask(str(task_name))
        base = registry.defaults[task]
        if not isinstance(payload, Mapping):
            return
        merged = dict(payload)
        merged["task"] = task.value
        template = PromptTemplate.from_dict(merged, variables=base.variables)
        if provider_id or profile_id:
            registry.register_override(template, provider_id=provider_id, profile_id=profile_id)
        else:
            registry.register_default(template)
    except (KeyError, ValueError, TypeError, PromptTemplateError):
        return


def _normalize_scoring_presets(raw: Any) -> list[dict[str, Any]]:
    from .scoring import ScoringPreset, recommended_preset

    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for payload in raw if isinstance(raw, list) else []:
        if not isinstance(payload, Mapping):
            continue
        try:
            preset = ScoringPreset.from_dict(payload)
        except (ValueError, TypeError):
            continue
        if preset.id not in seen:
            result.append(_merge_known(payload, preset.to_dict()))
            seen.add(preset.id)
    return result or [recommended_preset().to_dict()]


def _merge_known(original: Any, canonical: Mapping[str, Any]) -> dict[str, Any]:
    """Overlay validated known values while recursively retaining extensions."""
    result = deepcopy(dict(original)) if isinstance(original, Mapping) else {}
    for key, value in canonical.items():
        if isinstance(value, Mapping) and isinstance(result.get(key), Mapping):
            result[key] = _merge_known(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def _safe_int(value: Any, default: int, *, minimum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= minimum else default


def _safe_float(value: Any, default: float, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if minimum <= parsed <= maximum else default


def normalize_llm_api_profiles(config):
    """Return safe named LLM configs, migrating the legacy single config."""
    profiles = []
    for item in config.get("llm_api_profiles") or []:
        if not isinstance(item, dict) or not str(item.get("id") or "").strip():
            continue
        profile = dict(item)
        profile["temperature"] = _safe_float(profile.get("temperature"), DEFAULT_CONFIG["temperature"], 0, 2)
        profile["max_tokens"] = _safe_int(profile.get("max_tokens"), DEFAULT_CONFIG["max_tokens"], minimum=1)
        profile_reasoning = profile.get("reasoning") if isinstance(profile.get("reasoning"), Mapping) else {}
        normalized_reasoning = deepcopy(dict(profile_reasoning))
        for key in ("mode", "control", "effort", "budget_tokens"):
            normalized_reasoning.pop(key, None)
        normalized_reasoning.update(reasoning_intent_to_dict(reasoning_intent_from_config(profile_reasoning)))
        profile["reasoning"] = normalized_reasoning
        profiles.append(profile)
    if not profiles and any(config.get(key) for key in ("api_key", "base_url", "model")):
        profiles.append({
            "id": "default", "name": "Default",
            "provider_id": config.get("selected_provider_profile") or "custom",
            "base_url": config.get("base_url") or "", "model": config.get("model") or "",
            "api_key": config.get("api_key") or "", "temperature": config.get("temperature", 0.7),
            "max_tokens": config.get("max_tokens", 30000),
            "reasoning": reasoning_intent_to_dict(reasoning_intent_from_config(config.get("reasoning"))),
        })
    return profiles


def activate_llm_api_profile(config, profile_id):
    profiles = normalize_llm_api_profiles(config)
    profile = next((item for item in profiles if item["id"] == profile_id), None)
    if profile is None:
        return False
    config["llm_api_profiles"] = profiles
    config["selected_llm_api_profile_id"] = profile["id"]
    for source, target in (("provider_id", "selected_provider_profile"), ("base_url", "base_url"),
                           ("model", "model"), ("api_key", "api_key"),
                           ("temperature", "temperature"), ("max_tokens", "max_tokens"),
                           ("reasoning", "reasoning")):
        config[target] = profile.get(source, DEFAULT_CONFIG.get(target))
    return True
