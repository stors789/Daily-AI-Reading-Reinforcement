"""Prompt-building functions shared by every DAIRR shell."""

from __future__ import annotations

from typing import Any

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
