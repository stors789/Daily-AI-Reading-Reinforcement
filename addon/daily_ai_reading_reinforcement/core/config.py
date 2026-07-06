# Pure configuration constants, extracted from __init__.py.
# These do not depend on Anki/aqt/mw/gui_hooks.

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
    "temperature": 0.7,
    "max_tokens": 30000,
    "prompt_template": "",
    "deck_field_config": {},
    "last_selected_deck_id": "",
    "collapsed_deck_groups": [],
    "ui_language": "zh",
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
