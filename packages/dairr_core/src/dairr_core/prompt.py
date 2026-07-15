"""Prompt-building functions shared by every DAIRR shell."""

from __future__ import annotations

from typing import Any

from .config import prompt_registry_from_config
from .prompt_templates import PromptTask, PromptTemplate, RenderedPrompt, ResponseMode, render_prompt
from .utils import word_range_bounds


def writing_language_for_ui(ui_language: str) -> str:
    return {
        "zh": "中文",
        "en": "English",
        "ja": "日本語",
    }.get(ui_language, "中文")


def build_prompt(
    config: dict[str, Any],
    deck_name_value: str,
    cards: list[Any],
    selected_fields: list[str],
    preset: dict[str, str],
) -> str:
    ui_lang = writing_language_for_ui(str(config.get("ui_language") or "zh"))
    reader_native_language = str(
        preset.get("reader_native_language") or ui_lang or "English"
    )
    article_language = str(
        preset.get("article_language") or "the language being learned"
    )
    difficulty = str(preset.get("difficulty") or "appropriate for the learner")
    max_words = str(preset.get("max_words") or "")
    bounds = word_range_bounds(max_words)
    if bounds and bounds[0] != bounds[1]:
        length_instruction = (
            f"Write between about {bounds[0]} and {bounds[1]} words or characters."
        )
    elif bounds:
        length_instruction = f"Write about {bounds[0]} words or characters."
    else:
        length_instruction = "No fixed length limit."
    instructions = str(preset.get("instructions") or "No extra formatting instructions.")
    card_lines = []
    for index, card in enumerate(cards[:80], start=1):
        labels = []
        if card.is_new:
            labels.append("new")
        if card.is_failed:
            labels.append("failed")
        label = ", ".join(labels) if labels else "studied"
        field_context = "; ".join(
            f"{name}: {card.fields.get(name)}"
            for name in selected_fields
            if card.fields.get(name)
        )
        if field_context:
            card_lines.append(f"{index}. ({label}) {field_context}")
        else:
            card_lines.append(f"{index}. ({label})")

    default_prompt = (
        "You are generating a reading reinforcement text for a language learner.\n\n"
        "Inputs:\n"
        "- Reader native language: {reader_native_language}\n"
        "- Article language: {article_language}\n"
        "- Difficulty: {difficulty}\n"
        "- Length limit: {length_instruction}\n"
        "- Formatting requirements: {instructions}\n\n"
        "Use the provided card fields as source material.\n\n"
        "Output format:\n"
        "[ARTICLE_TITLE]\n"
        "A short title in the article language.\n\n"
        "[MAIN_ARTICLE]\n"
        "The main article. Use only the article language.\n"
        "IMPORTANT: After EACH paragraph, add a new line starting with [T] followed by a "
        "translation of that paragraph in the reader native language ({reader_native_language}). "
        "Example:\n"
        "First paragraph text in article language.\n"
        "[T] Translation of first paragraph in reader native language.\n\n"
        "Second paragraph text in article language.\n"
        "[T] Translation of second paragraph in reader native language.\n\n"
        "[REVIEW_NOTES]\n"
        "One note per important source term. Use this line format:\n"
        "- term :: explanation\n\n"
        "Constraints:\n"
        "- Return exactly the three bracketed blocks above.\n"
        "- Do not output Markdown headings.\n"
        "- Do not output HTML.\n"
        "- Follow the requested article language even if source fields contain other languages.\n"
        "- Do not use the reader native language in [MAIN_ARTICLE] except in [T] translation lines.\n"
        "- Use the reader native language for explanations in [REVIEW_NOTES].\n"
        "- Every paragraph in [MAIN_ARTICLE] must be followed by a [T] translation line.\n"
        "- Follow the length limit.\n"
        "- Preserve source terms accurately when they are the learning targets.\n"
        "- Do not add sections outside the blocks above.\n\n"
        "Cards:\n{cards}\n"
    )
    template = str(
        preset.get("prompt_template") or config.get("prompt_template") or default_prompt
    )
    return template.format(
        reader_native_language=reader_native_language,
        article_language=article_language,
        difficulty=difficulty,
        max_words=max_words,
        length_instruction=length_instruction,
        instructions=instructions,
        deck_name=deck_name_value,
        cards="\n".join(card_lines),
    )


def render_article_prompt(
    config: dict[str, Any],
    deck_name_value: str,
    cards: list[Any],
    selected_fields: list[str],
    preset: dict[str, Any],
) -> RenderedPrompt:
    """Render the exact article messages submitted by the LLM transport.

    New prompt presets resolve profile > provider > task default through the
    shared registry. Historical ``prompt_template`` values remain complete user
    prompt replacements and use plain-text response mode because their output
    contract is not known to DAIRR.
    """
    provider_id = str(config.get("selected_provider_profile") or "custom")
    profile_id = str(config.get("selected_llm_api_profile_id") or "")
    registry = prompt_registry_from_config(config)
    template = registry.resolve(
        PromptTask.ARTICLE_GENERATION,
        provider_id=provider_id,
        profile_id=profile_id,
    )
    legacy_template = str(preset.get("prompt_template") or config.get("prompt_template") or "")
    legacy_config = "ai_prompt_config" not in config
    if legacy_template or legacy_config:
        # build_prompt performs the legacy variable validation/rendering. Treat
        # the result as literal content so braces in card text remain harmless.
        rendered_legacy = build_prompt(config, deck_name_value, cards, selected_fields, preset)
        template = PromptTemplate(
            task=PromptTask.ARTICLE_GENERATION,
            system_template=str(
                config.get("system_prompt_template")
                or "Follow the requested output format and language boundaries exactly."
            ),
            user_template="{source_text}",
            response_mode=ResponseMode.PLAIN_TEXT,
            variables=template.variables,
            name="Migrated legacy article prompt",
        )
        return render_prompt(template, _article_prompt_values(config, deck_name_value, cards, selected_fields, preset, source_text=rendered_legacy))
    return render_prompt(
        template,
        _article_prompt_values(config, deck_name_value, cards, selected_fields, preset),
    )


def preview_article_prompt(
    config: dict[str, Any],
    deck_name_value: str,
    cards: list[Any],
    selected_fields: list[str],
    preset: dict[str, Any],
) -> dict[str, Any]:
    """Return the complete intentional preview, including technical contract."""
    return render_article_prompt(config, deck_name_value, cards, selected_fields, preset).preview()


def _article_prompt_values(
    config: dict[str, Any],
    deck_name_value: str,
    cards: list[Any],
    selected_fields: list[str],
    preset: dict[str, Any],
    *,
    source_text: str | None = None,
) -> dict[str, str]:
    ui_lang = writing_language_for_ui(str(config.get("ui_language") or "zh"))
    card_lines: list[str] = []
    terms: list[str] = []
    for card in cards[:80]:
        field_context = "; ".join(
            f"{name}: {card.fields.get(name)}"
            for name in selected_fields
            if card.fields.get(name)
        )
        if field_context:
            card_lines.append(field_context)
        term = str(getattr(card, "term", "") or "").strip()
        if term:
            terms.append(term)
    target_groups = preset.get("target_categories") if isinstance(preset.get("target_categories"), dict) else {}

    def joined(name: str) -> str:
        value = target_groups.get(name, preset.get(f"{name}_targets", ""))
        if isinstance(value, (list, tuple)):
            return "\n".join(str(item) for item in value)
        return str(value or "")

    desired = str(preset.get("max_words") or "")
    return {
        "source_text": source_text if source_text is not None else f"Deck: {deck_name_value}\n" + "\n".join(card_lines),
        "source_language": str(preset.get("reader_native_language") or ui_lang),
        "target_language": str(preset.get("article_language") or "the language being learned"),
        "proficiency_level": str(preset.get("difficulty") or "appropriate for the learner"),
        "selected_vocabulary": "\n".join(terms),
        "required_targets": joined("required"),
        "preferred_targets": joined("preferred"),
        "optional_targets": joined("optional") or "\n".join(terms),
        "excluded_targets": joined("excluded"),
        "article_genre": str(preset.get("genre") or "reading reinforcement"),
        "desired_length": desired or "No fixed length limit.",
        "custom_instructions": str(preset.get("instructions") or ""),
    }
