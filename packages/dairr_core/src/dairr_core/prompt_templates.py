"""Visible, validated prompt templates shared by every DAIRR host.

This module deliberately stops at rendering messages.  It performs no network
I/O and never appends hidden instructions after a template has been rendered.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from string import Formatter
from typing import Any, Iterable, Mapping


class PromptTask(str, Enum):
    ARTICLE_GENERATION = "article_generation"
    TRANSLATION_REVIEW = "translation_review"
    BACK_TRANSLATION_REVIEW = "back_translation_review"
    TARGET_USAGE_VALIDATION = "target_usage_validation"
    TEXT_SEGMENTATION = "text_segmentation"
    PREPROCESSING = "preprocessing"


class ResponseMode(str, Enum):
    STRUCTURED = "structured"
    PLAIN_TEXT = "plain_text"


class PromptTemplateError(ValueError):
    """A safe, user-correctable template validation error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class VariableSpec:
    name: str
    description: str
    required: bool = False
    example: str = ""


@dataclass(frozen=True, slots=True)
class PromptTemplate:
    task: PromptTask
    system_template: str
    user_template: str
    response_mode: ResponseMode
    response_contract: str = ""
    variables: tuple[VariableSpec, ...] = ()
    version: int = 1
    name: str = ""

    def __post_init__(self) -> None:
        if self.version < 1:
            raise PromptTemplateError("invalid_version", "Prompt template version must be positive.")
        names = [item.name for item in self.variables]
        if len(names) != len(set(names)):
            raise PromptTemplateError("duplicate_variable", "Prompt variable names must be unique.")
        if self.response_mode is ResponseMode.STRUCTURED:
            used = _field_names(self.system_template) | _field_names(self.user_template)
            if "output_format_contract" not in used:
                raise PromptTemplateError(
                    "hidden_response_contract",
                    "Structured prompts must include {output_format_contract} in a visible template.",
                )
            if not self.response_contract.strip():
                raise PromptTemplateError(
                    "missing_response_contract",
                    "Structured prompts require a visible response contract.",
                )

    @property
    def documented_variables(self) -> tuple[VariableSpec, ...]:
        contract = VariableSpec(
            "output_format_contract",
            "The complete visible response/parser contract for structured mode.",
            self.response_mode is ResponseMode.STRUCTURED,
        )
        return (*self.variables, contract)

    def with_custom_text(
        self,
        *,
        system_template: str,
        user_template: str,
        response_mode: ResponseMode | None = None,
        response_contract: str | None = None,
        name: str | None = None,
    ) -> "PromptTemplate":
        """Return a complete replacement without silently retaining wording."""
        selected_mode = response_mode or self.response_mode
        if response_contract is None:
            selected_contract = self.response_contract if selected_mode is self.response_mode else ""
        else:
            selected_contract = response_contract
        return replace(
            self,
            system_template=system_template,
            user_template=user_template,
            response_mode=selected_mode,
            response_contract=selected_contract,
            name=self.name if name is None else name,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task.value,
            "name": self.name,
            "version": self.version,
            "system_template": self.system_template,
            "user_template": self.user_template,
            "response_mode": self.response_mode.value,
            "response_contract": self.response_contract,
        }

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
        *,
        variables: Iterable[VariableSpec] = (),
    ) -> "PromptTemplate":
        try:
            task = PromptTask(str(data["task"]))
            mode = ResponseMode(str(data["response_mode"]))
        except (KeyError, ValueError) as exc:
            raise PromptTemplateError("invalid_template", "Prompt task or response mode is invalid.") from exc
        return cls(
            task=task,
            name=str(data.get("name") or ""),
            version=int(data.get("version") or 1),
            system_template=str(data.get("system_template") or ""),
            user_template=str(data.get("user_template") or ""),
            response_mode=mode,
            response_contract=str(data.get("response_contract") or ""),
            variables=tuple(variables),
        )


@dataclass(frozen=True, slots=True)
class RenderedPrompt:
    task: PromptTask
    system: str
    user: str
    response_mode: ResponseMode
    response_contract: str
    template_version: int
    used_variables: tuple[str, ...]

    @property
    def messages(self) -> tuple[dict[str, str], ...]:
        messages: list[dict[str, str]] = []
        if self.system:
            messages.append({"role": "system", "content": self.system})
        messages.append({"role": "user", "content": self.user})
        return tuple(messages)

    def preview(self) -> dict[str, Any]:
        """Return the exact non-secret messages that will be submitted."""
        return {
            "task": self.task.value,
            "responseMode": self.response_mode.value,
            "responseContract": self.response_contract,
            "messages": [dict(item) for item in self.messages],
            "templateVersion": self.template_version,
        }


def render_prompt(template: PromptTemplate, values: Mapping[str, Any]) -> RenderedPrompt:
    allowed = {item.name for item in template.documented_variables}
    supplied = dict(values)
    supplied["output_format_contract"] = template.response_contract
    system_fields = _validate_template_text(template.system_template, allowed, supplied)
    user_fields = _validate_template_text(template.user_template, allowed, supplied)
    fields = system_fields | user_fields
    try:
        system = template.system_template.format_map(_StrictValues(supplied))
        user = template.user_template.format_map(_StrictValues(supplied))
    except (KeyError, ValueError) as exc:
        raise PromptTemplateError(
            "render_failed",
            "Prompt rendering failed; check variables and literal braces.",
        ) from exc
    return RenderedPrompt(
        task=template.task,
        system=system,
        user=user,
        response_mode=template.response_mode,
        response_contract=template.response_contract,
        template_version=template.version,
        used_variables=tuple(sorted(fields)),
    )


class _StrictValues(dict[str, Any]):
    def __missing__(self, key: str) -> Any:
        raise KeyError(key)


def _validate_template_text(
    text: str,
    allowed: set[str],
    values: Mapping[str, Any],
) -> set[str]:
    try:
        parsed = list(Formatter().parse(text))
    except ValueError as exc:
        raise PromptTemplateError(
            "invalid_braces",
            "Prompt contains an unmatched brace. Use {{ and }} for literal braces.",
        ) from exc
    fields: set[str] = set()
    for _literal, field_name, format_spec, conversion in parsed:
        if field_name is None:
            continue
        if not field_name or "." in field_name or "[" in field_name or "]" in field_name:
            raise PromptTemplateError("unsafe_variable", "Prompt variables must be simple documented names.")
        if conversion or format_spec:
            raise PromptTemplateError(
                "unsupported_format",
                "Prompt variables do not support conversions or format specs.",
            )
        if field_name not in allowed:
            raise PromptTemplateError("unknown_variable", f"Unknown prompt variable: {field_name}")
        if field_name not in values or values[field_name] is None:
            raise PromptTemplateError("missing_variable", f"Missing prompt variable: {field_name}")
        fields.add(field_name)
    return fields


def _field_names(text: str) -> set[str]:
    try:
        return {field for _, field, _, _ in Formatter().parse(text) if field}
    except ValueError as exc:
        raise PromptTemplateError("invalid_braces", "Prompt contains an unmatched brace.") from exc


@dataclass(slots=True)
class PromptRegistry:
    defaults: dict[PromptTask, PromptTemplate] = field(default_factory=dict)
    provider_overrides: dict[tuple[PromptTask, str], PromptTemplate] = field(default_factory=dict)
    profile_overrides: dict[tuple[PromptTask, str], PromptTemplate] = field(default_factory=dict)

    def register_default(self, template: PromptTemplate) -> None:
        self.defaults[template.task] = template

    def register_override(
        self,
        template: PromptTemplate,
        *,
        provider_id: str = "",
        profile_id: str = "",
    ) -> None:
        if bool(provider_id) == bool(profile_id):
            raise PromptTemplateError(
                "invalid_override_scope",
                "Choose exactly one provider or profile override scope.",
            )
        target = self.profile_overrides if profile_id else self.provider_overrides
        target[(template.task, profile_id or provider_id)] = template

    def resolve(
        self,
        task: PromptTask,
        *,
        provider_id: str = "",
        profile_id: str = "",
    ) -> PromptTemplate:
        if profile_id and (task, profile_id) in self.profile_overrides:
            return self.profile_overrides[(task, profile_id)]
        if provider_id and (task, provider_id) in self.provider_overrides:
            return self.provider_overrides[(task, provider_id)]
        try:
            return self.defaults[task]
        except KeyError as exc:
            raise PromptTemplateError("missing_task", f"No prompt is registered for {task.value}.") from exc

    def render(
        self,
        task: PromptTask,
        values: Mapping[str, Any],
        *,
        provider_id: str = "",
        profile_id: str = "",
    ) -> RenderedPrompt:
        return render_prompt(
            self.resolve(task, provider_id=provider_id, profile_id=profile_id),
            values,
        )


def _vars(*items: tuple[str, str, bool]) -> tuple[VariableSpec, ...]:
    return tuple(VariableSpec(name, description, required) for name, description, required in items)


_ARTICLE_VARS = _vars(
    ("source_text", "Optional source/card context.", False),
    ("source_language", "Language of source material.", False),
    ("target_language", "Language of the generated article.", True),
    ("proficiency_level", "Requested learner proficiency.", False),
    ("selected_vocabulary", "All selected learning targets.", False),
    ("required_targets", "Targets that must be used naturally.", False),
    ("preferred_targets", "Targets to prefer when natural.", False),
    ("optional_targets", "Targets that may be omitted.", False),
    ("excluded_targets", "Targets that must not be used as learning targets.", False),
    ("article_genre", "Requested genre.", False),
    ("desired_length", "Requested length.", False),
    ("custom_instructions", "User-provided generation instructions.", False),
)

_REVIEW_VARS = _vars(
    ("source_text", "Text whose meaning should be preserved.", True),
    ("source_language", "Language of the source text.", True),
    ("target_language", "Language expected in the translation.", True),
    ("user_translation", "The learner's translation.", True),
    ("reference_translation", "Optional comparison translation; empty when absent.", False),
    ("proficiency_level", "Optional proficiency target.", False),
    ("custom_instructions", "User-provided review instructions.", False),
)

_REVIEW_CONTRACT = """Return one JSON object with optional string or string-list fields:
meaning, omissions_additions, grammar, vocabulary, naturalness,
register_style, suggested_revision, and overall.
Do not add a canonical reference when none was supplied."""


def default_prompt_registry() -> PromptRegistry:
    """Build a fresh registry containing every major model-powered workflow."""
    templates = [
        PromptTemplate(
            PromptTask.ARTICLE_GENERATION,
            "You create coherent language-learning reading material. Follow only the visible request and contract.",
            """Generate a {target_language} article.
Proficiency: {proficiency_level}
Genre: {article_genre}
Length: {desired_length}
Source context: {source_text}
Selected vocabulary: {selected_vocabulary}
Required targets: {required_targets}
Preferred targets: {preferred_targets}
Optional targets: {optional_targets}
Excluded targets: {excluded_targets}
Custom instructions:
{custom_instructions}

Response contract:
{output_format_contract}""",
            ResponseMode.STRUCTURED,
            """Return JSON with title, article, paragraph_translations, target_usage, and unused_targets.
Each target_usage item must identify the target, category, and actual surface form.
Optional targets may be omitted when they would reduce coherence.""",
            _ARTICLE_VARS,
            name="DAIRR article generation",
        ),
        PromptTemplate(
            PromptTask.TRANSLATION_REVIEW,
            "You are a careful language tutor. Accept valid alternatives and never demand verbatim reconstruction.",
            """Review the learner translation directly against the source.
Source language: {source_language}
Target language: {target_language}
Proficiency: {proficiency_level}
Source:
{source_text}

Learner translation:
{user_translation}

There is no authoritative reference translation. Do not invent one.
Custom review instructions:
{custom_instructions}

Response contract:
{output_format_contract}""",
            ResponseMode.STRUCTURED,
            _REVIEW_CONTRACT,
            _REVIEW_VARS,
            name="Translation review without reference",
        ),
        PromptTemplate(
            PromptTask.BACK_TRANSLATION_REVIEW,
            "You are a careful language tutor. Treat the reference as one comparison point, not the only valid answer.",
            """Review meaning, grammar, naturalness, register, tone, and useful stylistic similarities.
Source language: {source_language}
Target language: {target_language}
Proficiency: {proficiency_level}
Source:
{source_text}

Learner translation:
{user_translation}

Reference translation:
{reference_translation}

Custom review instructions:
{custom_instructions}

Response contract:
{output_format_contract}""",
            ResponseMode.STRUCTURED,
            _REVIEW_CONTRACT,
            _REVIEW_VARS,
            name="Reference-aware back-translation review",
        ),
        PromptTemplate(
            PromptTask.TARGET_USAGE_VALIDATION,
            "Validate target usage without forcing optional vocabulary or literal surface forms.",
            """Article:
{source_text}

Required: {required_targets}
Preferred: {preferred_targets}
Optional: {optional_targets}
Excluded: {excluded_targets}

Response contract:
{output_format_contract}""",
            ResponseMode.STRUCTURED,
            "Return JSON with target_usage and unused_targets; include actual surface forms and concise reasons.",
            _ARTICLE_VARS,
            name="Target usage validation",
        ),
        PromptTemplate(
            PromptTask.TEXT_SEGMENTATION,
            "Segment prose without rewriting, translating, summarizing, or dropping content.",
            """Source language: {source_language}
Segmentation instructions: {segmentation_instructions}
Text:
{source_text}

Response contract:
{output_format_contract}""",
            ResponseMode.STRUCTURED,
            "Return JSON with segments, an ordered array of objects containing id and exact source_text.",
            _vars(
                ("source_text", "Text to segment exactly.", True),
                ("source_language", "Source language.", False),
                ("segmentation_instructions", "User segmentation preferences.", False),
            ),
            name="Text segmentation",
        ),
        PromptTemplate(
            PromptTask.PREPROCESSING,
            "Apply only the requested preprocessing operation and preserve private content faithfully.",
            """Source language: {source_language}
Instructions:
{custom_instructions}

Text:
{source_text}

Return only the processed text.""",
            ResponseMode.PLAIN_TEXT,
            "",
            _vars(
                ("source_text", "Text to preprocess.", True),
                ("source_language", "Source language.", False),
                ("custom_instructions", "Requested preprocessing operation.", True),
            ),
            name="Text preprocessing",
        ),
    ]
    registry = PromptRegistry()
    for template in templates:
        registry.register_default(template)
    return registry
