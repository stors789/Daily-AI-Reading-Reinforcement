"""Target-aware article generation and defensive response recovery."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import json
import re
from typing import Any, Iterable, Mapping

from .operations import (
    CompletionTransport,
    ModelRequestSettings,
    ModelResponse,
    OperationContext,
    OperationError,
    run_completion,
)
from .prompt_templates import PromptRegistry, PromptTask, RenderedPrompt, ResponseMode
from .provider_capabilities import ProviderCapabilities
from .provider_requests import BuiltProviderRequest
from .response_parsing import ParsedModelResponse, ResponseParseError, parse_model_response
from .target_selection import TargetCategory


MAX_RESPONSE_CHARACTERS = 2_000_000
MAX_ARTICLE_CHARACTERS = 500_000
MAX_TARGETS = 1_000
MAX_SOURCE_CHARACTERS = 500_000
MAX_INSTRUCTION_CHARACTERS = 100_000
MAX_TARGET_CHARACTERS = 500_000


class TargetOutcomeStatus(str, Enum):
    EXACT = "exact"
    INFLECTED = "inflected"
    EQUIVALENT = "equivalent"
    USED = "used"
    UNUSABLE = "unusable"
    UNREPORTED = "unreported"
    EXCLUDED = "excluded"
    EXCLUDED_VIOLATION = "excluded_violation"


@dataclass(frozen=True, slots=True)
class GenerationTarget:
    id: str
    text: str
    category: TargetCategory
    equivalent_forms: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.text.strip():
            raise ValueError("generation targets require an id and text")
        if any(not value.strip() for value in self.equivalent_forms):
            raise ValueError("equivalent target forms cannot be empty")

    def prompt_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "target": self.text,
            "category": self.category.value,
            "equivalentForms": list(self.equivalent_forms),
        }


@dataclass(frozen=True, slots=True)
class ArticleGenerationRequest:
    target_language: str
    targets: tuple[GenerationTarget, ...] = ()
    source_text: str = ""
    source_language: str = ""
    proficiency_level: str = ""
    genre: str = ""
    desired_length: str = ""
    style: str = ""
    custom_instructions: str = ""

    def __post_init__(self) -> None:
        if not self.target_language.strip():
            raise ValueError("target language is required")
        if len(self.targets) > MAX_TARGETS:
            raise ValueError("too many article targets")
        if len(self.source_text) > MAX_SOURCE_CHARACTERS:
            raise ValueError("article source context exceeds the explicit size limit")
        if len(self.custom_instructions) + len(self.style) > MAX_INSTRUCTION_CHARACTERS:
            raise ValueError("article instructions exceed the explicit size limit")
        target_characters = sum(
            len(item.text) + sum(map(len, item.equivalent_forms))
            for item in self.targets
        )
        if target_characters > MAX_TARGET_CHARACTERS:
            raise ValueError("article target text exceeds the explicit size limit")
        ids = [item.id for item in self.targets]
        if len(ids) != len(set(ids)):
            raise ValueError("article target ids must be unique")

    def by_category(self, category: TargetCategory) -> tuple[GenerationTarget, ...]:
        return tuple(item for item in self.targets if item.category is category)

    def prompt_values(self) -> dict[str, str]:
        def encoded(items: Iterable[GenerationTarget]) -> str:
            return json.dumps(
                [item.prompt_dict() for item in items],
                ensure_ascii=False,
                separators=(",", ":"),
            )

        selected = tuple(item for item in self.targets if item.category is not TargetCategory.EXCLUDED)
        instructions = self.custom_instructions
        if self.style.strip():
            style_instruction = f"Requested style: {self.style.strip()}"
            instructions = f"{style_instruction}\n{instructions}" if instructions else style_instruction
        return {
            "source_text": self.source_text,
            "source_language": self.source_language,
            "target_language": self.target_language,
            "proficiency_level": self.proficiency_level,
            "selected_vocabulary": encoded(selected),
            "required_targets": encoded(self.by_category(TargetCategory.REQUIRED)),
            "preferred_targets": encoded(self.by_category(TargetCategory.PREFERRED)),
            "optional_targets": encoded(self.by_category(TargetCategory.OPTIONAL)),
            "excluded_targets": encoded(self.by_category(TargetCategory.EXCLUDED)),
            "article_genre": self.genre,
            "desired_length": self.desired_length,
            "custom_instructions": instructions,
        }


@dataclass(frozen=True, slots=True)
class TargetOutcome:
    target_id: str
    category: TargetCategory
    status: TargetOutcomeStatus
    actual_surface_forms: tuple[str, ...] = ()
    reason: str = ""

    @property
    def used(self) -> bool:
        return self.status in {
            TargetOutcomeStatus.EXACT,
            TargetOutcomeStatus.INFLECTED,
            TargetOutcomeStatus.EQUIVALENT,
            TargetOutcomeStatus.USED,
            TargetOutcomeStatus.EXCLUDED_VIOLATION,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "targetId": self.target_id,
            "category": self.category.value,
            "status": self.status.value,
            "used": self.used,
            "actualSurfaceForms": list(self.actual_surface_forms),
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class ArticleGenerationResult:
    title: str
    article: str
    paragraph_translations: tuple[str, ...]
    target_outcomes: tuple[TargetOutcome, ...]
    response_mode: ResponseMode
    warnings: tuple[str, ...] = ()
    possibly_truncated: bool = False
    recovered: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "article": self.article,
            "paragraphTranslations": list(self.paragraph_translations),
            "targetOutcomes": [item.to_dict() for item in self.target_outcomes],
            "responseMode": self.response_mode.value,
            "warnings": list(self.warnings),
            "possiblyTruncated": self.possibly_truncated,
            "recovered": self.recovered,
        }


@dataclass(frozen=True, slots=True)
class PreparedArticleGeneration:
    generation_request: ArticleGenerationRequest
    prompt: RenderedPrompt
    provider_request: BuiltProviderRequest
    operation_id: str


def prepare_article_generation(
    request: ArticleGenerationRequest,
    *,
    registry: PromptRegistry,
    provider_capabilities: ProviderCapabilities,
    request_settings: ModelRequestSettings,
    context: OperationContext,
    provider_id: str = "",
    profile_id: str = "",
) -> PreparedArticleGeneration:
    context.cancellation.raise_if_cancelled()
    prompt = registry.render(
        PromptTask.ARTICLE_GENERATION,
        request.prompt_values(),
        provider_id=provider_id,
        profile_id=profile_id,
    )
    provider_request = request_settings.build(provider_capabilities, prompt)
    context.cancellation.raise_if_cancelled()
    return PreparedArticleGeneration(request, prompt, provider_request, context.operation_id)


def complete_article_generation(
    prepared: PreparedArticleGeneration,
    response: ModelResponse,
    *,
    context: OperationContext,
) -> ArticleGenerationResult:
    if prepared.operation_id != context.operation_id:
        raise OperationError("operation_mismatch", "The article response no longer matches this request.")
    context.cancellation.raise_if_cancelled()
    result = parse_article_generation_response(
        prepared.generation_request,
        response.content,
        mode=prepared.prompt.response_mode,
        finish_reason=response.finish_reason,
    )
    context.cancellation.raise_if_cancelled()
    return result


def generate_target_aware_article(
    request: ArticleGenerationRequest,
    *,
    registry: PromptRegistry,
    provider_capabilities: ProviderCapabilities,
    request_settings: ModelRequestSettings,
    transport: CompletionTransport,
    context: OperationContext,
    provider_id: str = "",
    profile_id: str = "",
) -> ArticleGenerationResult:
    prepared = prepare_article_generation(
        request,
        registry=registry,
        provider_capabilities=provider_capabilities,
        request_settings=request_settings,
        context=context,
        provider_id=provider_id,
        profile_id=profile_id,
    )
    response = run_completion(transport, prepared.provider_request, context)
    return complete_article_generation(prepared, response, context=context)


def parse_article_generation_response(
    request: ArticleGenerationRequest,
    raw: Any,
    *,
    mode: ResponseMode,
    finish_reason: str | None = None,
) -> ArticleGenerationResult:
    text = _response_text(raw)
    if len(text) > MAX_RESPONSE_CHARACTERS:
        raise ResponseParseError("response_too_large", "The model response exceeded the safe size limit.")
    truncated = str(finish_reason or "").lower() in {"length", "max_tokens", "token_limit"}
    if mode is ResponseMode.PLAIN_TEXT:
        article = text.strip()
        if not article:
            raise ResponseParseError("empty_response", "The model returned an empty response.")
        if len(article) > MAX_ARTICLE_CHARACTERS:
            raise ResponseParseError("article_too_large", "The generated article exceeded the safe size limit.")
        return ArticleGenerationResult(
            "",
            article,
            (),
            _unreported_outcomes(request),
            mode,
            ("Plain-text mode does not provide verified target-usage mappings.",),
            truncated,
        )

    recovered_partial = False
    try:
        parsed = parse_model_response(text, ResponseMode.STRUCTURED, finish_reason=finish_reason)
    except ResponseParseError as exc:
        recovered_data = _recover_complete_article_fields(text)
        if not recovered_data:
            raise
        parsed = ParsedModelResponse(
            ResponseMode.STRUCTURED,
            data=recovered_data,
            warnings=("Recovered complete article fields from an otherwise malformed response.",),
            recovered_from_wrapper=True,
            possibly_truncated=exc.possibly_truncated or truncated,
        )
        recovered_partial = True
    data = parsed.data
    if not isinstance(data, Mapping):
        raise ResponseParseError("invalid_article", "The article response must be one JSON object.")
    return _structured_result(request, dict(data), parsed, recovered_partial)


def _structured_result(
    request: ArticleGenerationRequest,
    data: dict[str, Any],
    parsed: ParsedModelResponse,
    recovered_partial: bool,
) -> ArticleGenerationResult:
    warnings = list(parsed.warnings)
    title = _first_string(data, ("title", "article_title"))
    article = _first_string(data, ("article", "content", "text"))
    if not article:
        raise ResponseParseError("missing_article", "The structured response did not contain article text.")
    if len(article) > MAX_ARTICLE_CHARACTERS:
        raise ResponseParseError("article_too_large", "The generated article exceeded the safe size limit.")
    if not title:
        warnings.append("The response did not include an article title.")

    translations_value = _first_value(data, ("paragraph_translations", "translations"))
    translations, skipped_translations = _string_list(translations_value, nested_keys=("translation", "text"))
    if skipped_translations:
        warnings.append("Ignored invalid paragraph-translation entries.")

    usage_value = _first_value(data, ("target_usage", "usage", "targetUsage"))
    unused_value = _first_value(data, ("unused_targets", "unusable_targets", "unusedTargets"))
    outcomes, outcome_warnings = _target_outcomes(request, usage_value, unused_value)
    warnings.extend(outcome_warnings)
    known = {
        "title", "article_title", "article", "content", "text",
        "paragraph_translations", "translations", "target_usage", "usage",
        "targetUsage", "unused_targets", "unusable_targets", "unusedTargets",
    }
    unexpected_count = len(set(data) - known)
    if unexpected_count:
        warnings.append(f"Ignored {unexpected_count} unrecognized top-level response field(s).")
    return ArticleGenerationResult(
        title,
        article,
        translations,
        outcomes,
        ResponseMode.STRUCTURED,
        tuple(warnings),
        parsed.possibly_truncated,
        recovered_partial or parsed.recovered_from_wrapper,
    )


def _target_outcomes(
    request: ArticleGenerationRequest,
    usage_value: Any,
    unused_value: Any,
) -> tuple[tuple[TargetOutcome, ...], tuple[str, ...]]:
    targets = {item.id: item for item in request.targets}
    normalized: dict[str, list[GenerationTarget]] = {}
    for target in request.targets:
        for value in (target.text, *target.equivalent_forms):
            normalized.setdefault(_surface_key(value), []).append(target)

    warnings: list[str] = []
    usage_entries = _usage_entries(usage_value)
    used: dict[str, TargetOutcome] = {}
    unexpected = duplicate = invalid = 0
    for entry in usage_entries:
        if not isinstance(entry, Mapping):
            invalid += 1
            continue
        target = _match_target(dict(entry), targets, normalized)
        if target is None:
            unexpected += 1
            continue
        forms, _ = _string_list(
            _first_value(
                dict(entry),
                ("actual_surface_forms", "surface_forms", "actual_surface_form", "surface_form", "actual", "used_as"),
            )
        )
        if not forms:
            value = _first_string(dict(entry), ("usage",))
            forms = (value,) if value else ()
        reason = _first_string(dict(entry), ("reason", "explanation"))
        status = _usage_status(target, dict(entry), forms)
        if target.id in used:
            duplicate += 1
            prior = used[target.id]
            merged_forms = tuple(dict.fromkeys((*prior.actual_surface_forms, *forms)))
            used[target.id] = TargetOutcome(
                target.id,
                target.category,
                prior.status,
                merged_forms,
                prior.reason or reason,
            )
        else:
            used[target.id] = TargetOutcome(target.id, target.category, status, forms, reason)

    unusable: dict[str, str] = {}
    for entry in _unused_entries(unused_value):
        target: GenerationTarget | None
        reason = "The model reported that this target could not be used naturally."
        if isinstance(entry, Mapping):
            target = _match_target(dict(entry), targets, normalized)
            reason = _first_string(dict(entry), ("reason", "explanation")) or reason
        elif isinstance(entry, str):
            target = _match_surface(entry, normalized)
        else:
            target = None
            invalid += 1
        if target is None:
            unexpected += 1
        elif target.id in used:
            duplicate += 1
        else:
            unusable[target.id] = reason

    outcomes: list[TargetOutcome] = []
    missing_priority = 0
    excluded_violations = 0
    for target in request.targets:
        if target.id in used:
            outcome = used[target.id]
            if target.category is TargetCategory.EXCLUDED:
                outcome = TargetOutcome(
                    target.id,
                    target.category,
                    TargetOutcomeStatus.EXCLUDED_VIOLATION,
                    outcome.actual_surface_forms,
                    outcome.reason or "The response reported use of an excluded target.",
                )
                excluded_violations += 1
            outcomes.append(outcome)
        elif target.id in unusable:
            outcomes.append(TargetOutcome(
                target.id,
                target.category,
                TargetOutcomeStatus.UNUSABLE,
                reason=unusable[target.id],
            ))
        elif target.category is TargetCategory.EXCLUDED:
            outcomes.append(TargetOutcome(target.id, target.category, TargetOutcomeStatus.EXCLUDED))
        else:
            outcomes.append(TargetOutcome(
                target.id,
                target.category,
                TargetOutcomeStatus.UNREPORTED,
                reason="The response did not report usage or natural unusability for this target.",
            ))
            if target.category in {TargetCategory.REQUIRED, TargetCategory.PREFERRED}:
                missing_priority += 1
    if unexpected:
        warnings.append(f"Ignored {unexpected} unexpected target mapping(s).")
    if duplicate:
        warnings.append(f"Recovered {duplicate} duplicate or conflicting target mapping(s).")
    if invalid:
        warnings.append(f"Ignored {invalid} malformed target mapping(s).")
    if missing_priority:
        warnings.append(f"Usage was unreported for {missing_priority} required or preferred target(s).")
    if excluded_violations:
        warnings.append(f"The response reported {excluded_violations} excluded target usage violation(s).")
    return tuple(outcomes), tuple(warnings)


def _usage_entries(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, Mapping):
        if any(key in value for key in ("target", "target_id", "targetId", "id")):
            return [value]
        entries: list[dict[str, Any]] = []
        for key, item in value.items():
            if isinstance(item, Mapping):
                entries.append({"target": str(key), **dict(item)})
            else:
                entries.append({"target": str(key), "actual_surface_form": item})
        return entries
    return [] if value is None else [value]


def _unused_entries(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, Mapping):
        return [
            {"target": str(key), "reason": item} if isinstance(item, str)
            else {"target": str(key), **dict(item)} if isinstance(item, Mapping)
            else key
            for key, item in value.items()
        ]
    return [value] if isinstance(value, str) else []


def _match_target(
    entry: dict[str, Any],
    targets: Mapping[str, GenerationTarget],
    normalized: Mapping[str, list[GenerationTarget]],
) -> GenerationTarget | None:
    identifier = _first_string(entry, ("target_id", "targetId", "id"))
    if identifier and identifier in targets:
        return targets[identifier]
    surface = _first_string(entry, ("target", "text", "expression"))
    return _match_surface(surface, normalized) if surface else None


def _match_surface(
    value: str,
    normalized: Mapping[str, list[GenerationTarget]],
) -> GenerationTarget | None:
    matches = normalized.get(_surface_key(value), ())
    return matches[0] if len(matches) == 1 else None


def _usage_status(
    target: GenerationTarget,
    entry: dict[str, Any],
    forms: tuple[str, ...],
) -> TargetOutcomeStatus:
    declared = _first_string(entry, ("status", "usage_type", "match_type")).lower()
    aliases = {
        "exact": TargetOutcomeStatus.EXACT,
        "inflected": TargetOutcomeStatus.INFLECTED,
        "inflection": TargetOutcomeStatus.INFLECTED,
        "morphological": TargetOutcomeStatus.INFLECTED,
        "equivalent": TargetOutcomeStatus.EQUIVALENT,
        "used": TargetOutcomeStatus.USED,
    }
    if declared in aliases:
        return aliases[declared]
    keys = {_surface_key(value) for value in forms}
    if _surface_key(target.text) in keys:
        return TargetOutcomeStatus.EXACT
    if keys.intersection(_surface_key(value) for value in target.equivalent_forms):
        return TargetOutcomeStatus.EQUIVALENT
    return TargetOutcomeStatus.INFLECTED if forms else TargetOutcomeStatus.USED


def _unreported_outcomes(request: ArticleGenerationRequest) -> tuple[TargetOutcome, ...]:
    return tuple(
        TargetOutcome(
            target.id,
            target.category,
            TargetOutcomeStatus.EXCLUDED if target.category is TargetCategory.EXCLUDED else TargetOutcomeStatus.UNREPORTED,
            reason="" if target.category is TargetCategory.EXCLUDED else "Plain-text mode has no target-usage mapping.",
        )
        for target in request.targets
    )


def _recover_complete_article_fields(text: str) -> dict[str, str]:
    """Recover only completely decoded JSON string fields, never guessed text."""
    recovered: dict[str, str] = {}
    decoder = json.JSONDecoder()
    for canonical, names in (("title", ("title", "article_title")), ("article", ("article", "content", "text"))):
        for name in names:
            match = re.search(rf'"{re.escape(name)}"\s*:\s*', text)
            if not match:
                continue
            try:
                value, _end = decoder.raw_decode(text[match.end():])
            except json.JSONDecodeError:
                continue
            if isinstance(value, str) and value.strip():
                recovered[canonical] = value.strip()
                break
    return recovered if recovered.get("article") else {}


def _response_text(raw: Any) -> str:
    if isinstance(raw, str):
        return raw
    if isinstance(raw, Mapping):
        try:
            return json.dumps(dict(raw), ensure_ascii=False)
        except Exception as exc:
            raise ResponseParseError("invalid_response", "The model returned an invalid response object.") from exc
    raise ResponseParseError("invalid_response", "The model returned an invalid response type.")


def _first_value(data: Mapping[str, Any], names: Iterable[str]) -> Any:
    for name in names:
        if name in data:
            return data[name]
    return None


def _first_string(data: Mapping[str, Any], names: Iterable[str]) -> str:
    value = _first_value(data, names)
    return value.strip() if isinstance(value, str) else ""


def _string_list(
    value: Any,
    *,
    nested_keys: tuple[str, ...] = (),
) -> tuple[tuple[str, ...], int]:
    if isinstance(value, str):
        return ((value.strip(),) if value.strip() else ()), 0
    if not isinstance(value, list):
        return (), 0 if value is None else 1
    result: list[str] = []
    skipped = 0
    for item in value:
        text = item.strip() if isinstance(item, str) else _first_string(item, nested_keys) if isinstance(item, Mapping) else ""
        if text:
            result.append(text)
        else:
            skipped += 1
    return tuple(result), skipped


def _surface_key(value: str) -> str:
    return " ".join(str(value).casefold().split())
