"""Translation-review prompt selection and normalized response parsing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .prompt_templates import (
    PromptRegistry,
    PromptTask,
    RenderedPrompt,
    ResponseMode,
)
from .response_parsing import ParsedModelResponse, ResponseParseError, parse_model_response


REVIEW_CATEGORIES = (
    "meaning",
    "omissions_additions",
    "grammar",
    "vocabulary",
    "naturalness",
    "register_style",
)


@dataclass(frozen=True, slots=True)
class TranslationReviewRequest:
    source_text: str
    user_translation: str
    source_language: str
    target_language: str
    reference_translation: str | None = None
    proficiency_level: str = ""
    custom_instructions: str = ""

    @property
    def has_reference(self) -> bool:
        return bool((self.reference_translation or "").strip())

    def prompt_values(self) -> dict[str, str]:
        return {
            "source_text": self.source_text,
            "user_translation": self.user_translation,
            "source_language": self.source_language,
            "target_language": self.target_language,
            "reference_translation": self.reference_translation or "",
            "proficiency_level": self.proficiency_level,
            "custom_instructions": self.custom_instructions,
        }


@dataclass(frozen=True, slots=True)
class TranslationReviewResult:
    categories: Mapping[str, tuple[str, ...]]
    suggested_revision: str = ""
    overall: str = ""
    plain_text: str = ""
    reference_used: bool = False
    warnings: tuple[str, ...] = ()
    possibly_truncated: bool = False


def render_translation_review_prompt(
    registry: PromptRegistry,
    request: TranslationReviewRequest,
    *,
    provider_id: str = "",
    profile_id: str = "",
) -> RenderedPrompt:
    if not request.source_text.strip() or not request.user_translation.strip():
        raise ValueError("Source text and user translation are required.")
    task = PromptTask.BACK_TRANSLATION_REVIEW if request.has_reference else PromptTask.TRANSLATION_REVIEW
    return registry.render(
        task,
        request.prompt_values(),
        provider_id=provider_id,
        profile_id=profile_id,
    )


def parse_translation_review(
    raw: Any,
    *,
    mode: ResponseMode,
    reference_was_provided: bool,
    finish_reason: str | None = None,
) -> TranslationReviewResult:
    parsed = parse_model_response(raw, mode, finish_reason=finish_reason)
    if mode is ResponseMode.PLAIN_TEXT:
        return TranslationReviewResult(
            categories={},
            plain_text=parsed.text,
            reference_used=reference_was_provided,
            warnings=parsed.warnings,
            possibly_truncated=parsed.possibly_truncated,
        )
    return _structured_review(parsed, reference_was_provided)


def _structured_review(
    parsed: ParsedModelResponse,
    reference_was_provided: bool,
) -> TranslationReviewResult:
    data = parsed.data
    if not isinstance(data, dict):
        raise ResponseParseError("invalid_review", "The review response must be a JSON object.")
    categories: dict[str, tuple[str, ...]] = {}
    for key in REVIEW_CATEGORIES:
        values = _feedback_items(data.get(key))
        if values:
            categories[key] = values
    overall = _feedback_text(data.get("overall"))
    suggested = _feedback_text(data.get("suggested_revision"))
    if not categories and not overall and not suggested:
        raise ResponseParseError(
            "empty_review",
            "The structured response did not contain any recognized review feedback.",
        )
    warnings = list(parsed.warnings)
    unknown = sorted(set(data) - set(REVIEW_CATEGORIES) - {"overall", "suggested_revision", "reference_used"})
    if unknown:
        warnings.append("Ignored unrecognized review fields: " + ", ".join(unknown))
    # Whether a reference existed belongs to trusted request context.  A model
    # cannot turn a reference-free review into a canonical-answer comparison.
    if not reference_was_provided and data.get("reference_used"):
        warnings.append("Ignored a model claim that a reference translation was used.")
    return TranslationReviewResult(
        categories=categories,
        suggested_revision=suggested,
        overall=overall,
        reference_used=reference_was_provided,
        warnings=tuple(warnings),
        possibly_truncated=parsed.possibly_truncated,
    )


def _feedback_items(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        text = value.strip()
        return (text,) if text else ()
    if isinstance(value, list):
        return tuple(text for item in value if (text := _feedback_text(item)))
    if isinstance(value, dict):
        return tuple(
            f"{key}: {text}" for key, item in value.items() if (text := _feedback_text(item))
        )
    return ()


def _feedback_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    return ""
