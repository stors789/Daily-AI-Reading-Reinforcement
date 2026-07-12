"""Platform-agnostic DAIRR configuration defaults."""

from __future__ import annotations

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
}


def normalize_llm_api_profiles(config):
    """Return safe named LLM configs, migrating the legacy single config."""
    profiles = []
    for item in config.get("llm_api_profiles") or []:
        if not isinstance(item, dict) or not str(item.get("id") or "").strip():
            continue
        profiles.append(dict(item))
    if not profiles and any(config.get(key) for key in ("api_key", "base_url", "model")):
        profiles.append({
            "id": "default", "name": "Default",
            "provider_id": config.get("selected_provider_profile") or "custom",
            "base_url": config.get("base_url") or "", "model": config.get("model") or "",
            "api_key": config.get("api_key") or "", "temperature": config.get("temperature", 0.7),
            "max_tokens": config.get("max_tokens", 30000),
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
                           ("temperature", "temperature"), ("max_tokens", "max_tokens")):
        config[target] = profile.get(source, DEFAULT_CONFIG.get(target))
    return True
