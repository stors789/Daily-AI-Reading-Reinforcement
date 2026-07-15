"""Thin add-on host facade for DAIRR next-release shared services."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from threading import RLock
from typing import Any, Callable, Iterable, Mapping

try:
    from .dairr_core.article_generation import (  # type: ignore[import-not-found]
        ArticleGenerationRequest, GenerationTarget, generate_target_aware_article,
    )
    from .dairr_core.article import load_saved_article  # type: ignore[import-not-found]
    from .dairr_core.capabilities import (  # type: ignore[import-not-found]
        Capability, CapabilityId, CapabilityReason, CapabilitySet, CapabilityStatus, Provenance,
    )
    from .dairr_core.config import (  # type: ignore[import-not-found]
        export_prompt_registry_overrides, normalize_config, prompt_registry_from_config,
        reasoning_intent_from_config, reasoning_intent_to_dict,
    )
    from .dairr_core.llm import OpenAICompatibleTransport  # type: ignore[import-not-found]
    from .dairr_core.operations import (  # type: ignore[import-not-found]
        ModelRequestSettings, OperationContext, OperationError,
    )
    from .dairr_core.practice import (  # type: ignore[import-not-found]
        ArticleReference, PracticeSegment, TranslationDirection,
    )
    from .dairr_core.practice_repository import (  # type: ignore[import-not-found]
        PracticeRepository, session_document,
    )
    from .dairr_core.practice_service import PracticeService  # type: ignore[import-not-found]
    from .dairr_core.prompt_templates import (  # type: ignore[import-not-found]
        PromptTask, PromptTemplate, default_prompt_registry,
    )
    from .dairr_core.provider_capabilities import (  # type: ignore[import-not-found]
        ProviderConfigurationError, ReasoningControl, ReasoningIntent, ReasoningMode,
        known_provider_capabilities,
    )
    from .dairr_core.scoring import (  # type: ignore[import-not-found]
        ScoringPreset, SettingsMode, export_preset, import_preset, recommended_preset,
        score_cards, signal_metadata,
    )
    from .dairr_core.study_signals import CardStudySignals  # type: ignore[import-not-found]
    from .dairr_core.target_selection import TargetCategory  # type: ignore[import-not-found]
    from .dairr_core.target_selection import (  # type: ignore[import-not-found]
        ManualOverride, select_targets,
    )
    from .dairr_core.rendering import parse_article_response  # type: ignore[import-not-found]
except ImportError:
    from dairr_core.article_generation import (
        ArticleGenerationRequest, GenerationTarget, generate_target_aware_article,
    )
    from dairr_core.article import load_saved_article
    from dairr_core.capabilities import (
        Capability, CapabilityId, CapabilityReason, CapabilitySet, CapabilityStatus, Provenance,
    )
    from dairr_core.config import (
        export_prompt_registry_overrides, normalize_config, prompt_registry_from_config,
        reasoning_intent_from_config, reasoning_intent_to_dict,
    )
    from dairr_core.llm import OpenAICompatibleTransport
    from dairr_core.operations import ModelRequestSettings, OperationContext, OperationError
    from dairr_core.practice import ArticleReference, PracticeSegment, TranslationDirection
    from dairr_core.practice_repository import PracticeRepository, session_document
    from dairr_core.practice_service import PracticeService
    from dairr_core.prompt_templates import PromptTask, PromptTemplate, default_prompt_registry
    from dairr_core.provider_capabilities import (
        ProviderConfigurationError, ReasoningControl, ReasoningIntent, ReasoningMode,
        known_provider_capabilities,
    )
    from dairr_core.scoring import (
        ScoringPreset, SettingsMode, export_preset, import_preset, recommended_preset,
        score_cards, signal_metadata,
    )
    from dairr_core.study_signals import CardStudySignals
    from dairr_core.target_selection import TargetCategory
    from dairr_core.target_selection import ManualOverride, select_targets
    from dairr_core.rendering import parse_article_response


_CAMEL_BOUNDARY = re.compile(r"_([a-z])")


class AddonReleaseService:
    """Map bridge JSON to shared DAIRR services without retaining Anki/Qt state."""

    def __init__(
        self,
        load_config: Callable[[], Mapping[str, Any]],
        save_config: Callable[[dict[str, Any]], None],
        history_root: Path,
    ) -> None:
        self._load = load_config
        self._save = save_config
        self.repository = PracticeRepository(history_root / "practice_sessions")
        self.practice = PracticeService(self.repository)
        self._sessions: dict[str, Any] = {}
        self._revisions: dict[str, int] = {}
        self._session_lock = RLock()

    @property
    def history_root(self) -> Path:
        return self.repository.root.parent

    def capabilities(self, anki_capabilities: CapabilitySet) -> dict[str, Any]:
        declared = dict(anki_capabilities.to_dict())
        provider = self.provider_capabilities(self.config())
        for capability in (
            Capability(CapabilityId.ARTICLE_HISTORY, CapabilityStatus.AVAILABLE,
                       provenance=Provenance.LOCAL_HISTORY,
                       detail="Existing Markdown article history is available."),
            Capability(CapabilityId.PASTED_TEXT_PRACTICE, CapabilityStatus.AVAILABLE,
                       provenance=Provenance.SHARED_CORE,
                       detail="Pasted-text practice does not require Anki."),
            Capability(CapabilityId.CUSTOM_PROMPTS, CapabilityStatus.AVAILABLE,
                       provenance=Provenance.USER_CONFIGURED,
                       detail="All model workflow prompts and visible contracts are editable."),
            Capability(
                CapabilityId.PROVIDER_REASONING,
                CapabilityStatus.AVAILABLE if provider.supports_reasoning else CapabilityStatus.PROVIDER_UNSUPPORTED,
                CapabilityReason.NONE if provider.supports_reasoning else CapabilityReason.PROVIDER_LIMITATION,
                Provenance.PROVIDER_DECLARED,
                "Explicit controls depend on the selected provider.",
            ),
            Capability(CapabilityId.CANCELLATION, CapabilityStatus.AVAILABLE,
                       provenance=Provenance.SHARED_CORE,
                       detail="Long add-on operations use cooperative cancellation."),
        ):
            declared[capability.id.value] = capability.to_dict()
        limits = self.practice.segmentation_limits
        return {
            "capabilities": declared,
            "practiceLimits": {
                "maxSourceCharacters": limits.max_text_characters,
                "maxSegments": limits.max_segments,
                "maxSegmentCharacters": limits.max_segment_characters,
            },
        }

    # Practice ---------------------------------------------------------

    def create_pasted_practice(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        session = self.practice.create_pasted(
            str(payload.get("sourceText") or ""),
            str(payload.get("sourceLanguage") or ""),
            str(payload.get("targetLanguage") or ""),
            direction=_direction(payload.get("direction")),
            proficiency_level=_optional_text(payload.get("proficiencyLevel")),
            custom_review_instructions=str(payload.get("customReviewInstructions") or ""),
            save=bool(payload.get("save", False)),
        )
        self._remember_session(session)
        return {"session": self._session_payload(session), "saved": bool(payload.get("save", False))}

    def create_article_practice(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        direction = _direction(payload.get("direction"), article=True)
        raw_path = str(payload.get("articlePath") or "")
        loaded = load_saved_article(raw_path, articles_dir=self.history_root / "articles")
        derived_source, derived_references, derived_title = _article_practice_material(
            str(loaded.get("article") or ""), direction
        )
        references = payload.get("referenceParagraphs")
        reference_values = (
            tuple(None if value is None else str(value) for value in references)
            if isinstance(references, list)
            else tuple(derived_references)
        )
        source_text = str(payload.get("sourceText") or derived_source)
        article = ArticleReference(
            self._article_reference_path(raw_path),
            title=str(payload.get("title") or loaded.get("title") or derived_title),
            source_snapshot=source_text,
            reference_snapshot=(
                _optional_text(payload.get("referenceText"))
                or ("\n\n".join(value or "" for value in reference_values) if reference_values else None)
            ),
        )
        session = self.practice.create_from_article(
            source_text,
            str(payload.get("sourceLanguage") or ""),
            str(payload.get("targetLanguage") or ""),
            article,
            reference_paragraphs=reference_values,
            direction=direction,
            proficiency_level=_optional_text(payload.get("proficiencyLevel")),
            custom_review_instructions=str(payload.get("customReviewInstructions") or ""),
            save=bool(payload.get("save", True)),
        )
        self._remember_session(session)
        return {"session": self._session_payload(session), "saved": bool(payload.get("save", True))}

    def list_practice_sessions(self) -> dict[str, Any]:
        sessions = []
        for session_id in self.repository.list_ids():
            try:
                session = self.repository.load(session_id)
            except Exception:
                # One corrupt optional record must not hide the rest of history.
                continue
            sessions.append({
                "id": session.id,
                "kind": session.kind.value,
                "sourceLanguage": session.source_language,
                "targetLanguage": session.target_language,
                "status": session.status.value,
                "updatedAt": session.updated_at,
                "attemptCount": len(session.attempts),
            })
        sessions.sort(key=lambda item: item["updatedAt"], reverse=True)
        return {"sessions": sessions}

    def load_practice_session(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        session = self._load_session(_required_id(payload, "sessionId"))
        return {"session": self._session_payload(session)}

    def save_practice_draft(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        session = self._load_session(_required_id(payload, "sessionId"))
        self._check_revision(session.id, payload)
        persist = bool(payload.get("persist", payload.get("save", True)))
        session = self.practice.save_draft(
            session,
            str(payload.get("translation") or ""),
            segment_id=_optional_text(payload.get("segmentId")),
            persist=persist,
        )
        self._remember_session(session, increment_revision=True)
        return {"session": self._session_payload(session), "persisted": persist}

    def update_practice_segments(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        session = self._load_session(_required_id(payload, "sessionId"))
        self._check_revision(session.id, payload)
        if session.attempts:
            raise OperationError(
                "segmentation_locked",
                "Start a new session to edit segmentation after submitting an attempt.",
            )
        rows = payload.get("segments")
        if not isinstance(rows, list) or not rows:
            raise OperationError("invalid_segments", "At least one practice segment is required.")
        segments = tuple(
            PracticeSegment(
                str(row.get("id") or f"segment-{index + 1}"),
                index,
                str(row.get("sourceText") or ""),
                _optional_text(row.get("referenceText")),
            )
            for index, row in enumerate(rows)
            if isinstance(row, Mapping)
        )
        updated = session.with_segments(segments)
        self._remember_session(updated, increment_revision=True)
        if bool(payload.get("persist", payload.get("save", True))):
            self.practice.save_session(updated)
        return {"session": self._session_payload(updated)}

    def delete_practice_session(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        session_id = _required_id(payload, "sessionId")
        with self._session_lock:
            known_in_memory = self._sessions.pop(session_id, None) is not None
            self._revisions.pop(session_id, None)
        return {"sessionId": session_id, "deleted": self.repository.delete(session_id) or known_in_memory}

    def submit_practice_review(
        self,
        payload: Mapping[str, Any],
        context: OperationContext,
    ) -> dict[str, Any]:
        config = self.config()
        session = self._load_session(_required_id(payload, "sessionId"))
        self._check_revision(session.id, payload)
        completed = self.practice.review(
            session,
            str(payload.get("translation") or ""),
            registry=prompt_registry_from_config(config),
            provider_capabilities=self.provider_capabilities(config),
            request_settings=self.request_settings(config),
            transport=OpenAICompatibleTransport(config),
            context=context,
            segment_id=_optional_text(payload.get("segmentId")),
            revision_of=_optional_text(payload.get("revisionOf")),
            provider_id=str(config.get("selected_provider_profile") or ""),
            profile_id=str(config.get("selected_llm_api_profile_id") or ""),
            persist=bool(payload.get("persist", payload.get("save", True))),
        )
        self._remember_session(completed.session, increment_revision=True)
        return {
            "session": self._session_payload(completed.session),
            "attemptId": completed.attempt_id,
            "review": _json_value(completed.result),
        }

    # Scoring ----------------------------------------------------------

    def get_scoring_config(self) -> dict[str, Any]:
        config = self.config()
        presets = list(config.get("scoring_presets") or [])
        return {
            "presets": presets,
            "selectedPresetId": config.get("selected_scoring_preset_id"),
            "signalMetadata": {
                mode.value: [
                    {
                        "signal": item.name.value,
                        "label": item.label,
                        "explanation": item.explanation,
                        "simpleControl": item.simple_control,
                    }
                    for item in signal_metadata(mode)
                ]
                for mode in (SettingsMode.SIMPLE, SettingsMode.ADVANCED)
            },
        }

    def save_scoring_config(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        raw = payload.get("preset")
        if not isinstance(raw, Mapping):
            raise OperationError("invalid_scoring_preset", "A scoring preset object is required.")
        preset = ScoringPreset.from_dict(raw)
        config = self.config()
        presets = [item for item in config["scoring_presets"] if item.get("id") != preset.id]
        config["scoring_presets"] = [*presets, preset.to_dict()]
        config["selected_scoring_preset_id"] = preset.id
        self._save(config)
        return self.get_scoring_config()

    def reset_scoring_config(self) -> dict[str, Any]:
        config = self.config()
        preset = recommended_preset()
        config["scoring_presets"] = [preset.to_dict()]
        config["selected_scoring_preset_id"] = preset.id
        self._save(config)
        return self.get_scoring_config()

    def import_scoring_config(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        preset = import_preset(str(payload.get("serialized") or ""))
        return self.save_scoring_config({"preset": preset.to_dict()})

    def export_scoring_config(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        preset = self._selected_preset(_optional_text(payload.get("presetId")))
        return {"serialized": export_preset(preset), "presetId": preset.id}

    def preview_scoring(
        self,
        payload: Mapping[str, Any],
        signals: Iterable[CardStudySignals],
    ) -> dict[str, Any]:
        raw_preset = payload.get("preset")
        preset = (
            ScoringPreset.from_dict(raw_preset)
            if isinstance(raw_preset, Mapping)
            else self._selected_preset(_optional_text(payload.get("presetId")))
        )
        scores = score_cards(signals, preset)
        overrides = tuple(
            ManualOverride.from_dict(item)
            for item in (payload.get("manualOverrides") or [])
            if isinstance(item, Mapping)
        )
        selection = select_targets(
            scores,
            preset.selection,
            overrides,
            tuple(str(value) for value in (payload.get("explicitOrder") or ())),
        )
        return {"preset": preset.to_dict(), "selection": selection.to_dict()}

    @staticmethod
    def study_signals_payload(signals: Iterable[CardStudySignals]) -> list[dict[str, Any]]:
        return [_json_value(signal) for signal in signals]

    # Prompt/reasoning -------------------------------------------------

    def list_prompt_templates(self) -> dict[str, Any]:
        registry = prompt_registry_from_config(self.config())
        return {"templates": [self._template_payload(registry.resolve(task)) for task in PromptTask]}

    def get_prompt_template(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        task = PromptTask(str(payload.get("task") or ""))
        registry = prompt_registry_from_config(self.config())
        scope, provider_id, profile_id = _prompt_scope(payload)
        template = registry.resolve(
            task,
            provider_id=provider_id,
            profile_id=profile_id,
        )
        return {"template": self._template_payload(template), "scope": scope}

    def save_prompt_template(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        raw = payload.get("template")
        if not isinstance(raw, Mapping):
            raise OperationError("invalid_prompt_template", "A prompt template object is required.")
        config = self.config()
        registry = prompt_registry_from_config(config)
        task = PromptTask(str(raw.get("task") or ""))
        base = default_prompt_registry().defaults[task]
        normalized = _snake_prompt_payload(raw)
        normalized["task"] = task.value
        template = PromptTemplate.from_dict(normalized, variables=base.variables)
        scope, provider_id, profile_id = _prompt_scope(payload)
        if scope == "provider":
            registry.register_override(template, provider_id=provider_id)
        elif scope == "profile":
            registry.register_override(template, profile_id=profile_id)
        else:
            registry.register_default(template)
        config["ai_prompt_config"] = export_prompt_registry_overrides(
            registry, existing=config.get("ai_prompt_config")
        )
        self._save(config)
        return {"template": self._template_payload(template), "scope": scope}

    def reset_prompt_template(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        task = PromptTask(str(payload.get("task") or ""))
        config = self.config()
        scope, provider_id, profile_id = _prompt_scope(payload)
        prompt_config = deepcopy(config.get("ai_prompt_config") or {})
        if scope == "task":
            task_overrides = dict(prompt_config.get("task_overrides") or {})
            task_overrides.pop(task.value, None)
            prompt_config["task_overrides"] = task_overrides
        else:
            group_key = "provider_overrides" if scope == "provider" else "profile_overrides"
            identity = provider_id if scope == "provider" else profile_id
            groups = dict(prompt_config.get(group_key) or {})
            tasks = dict(groups.get(identity) or {})
            tasks.pop(task.value, None)
            if tasks:
                groups[identity] = tasks
            else:
                groups.pop(identity, None)
            prompt_config[group_key] = groups
        config["ai_prompt_config"] = prompt_config
        self._save(config)
        result = self.get_prompt_template(payload)
        result["scope"] = scope
        return result

    def export_prompt_templates(self) -> dict[str, Any]:
        config = self.config()
        return {
            "serialized": json.dumps(
                config.get("ai_prompt_config") or {},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        }

    def import_prompt_templates(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        try:
            raw = json.loads(str(payload.get("serialized") or ""))
        except json.JSONDecodeError as exc:
            raise OperationError("invalid_prompt_import", "Prompt settings are not valid JSON.") from exc
        if not isinstance(raw, Mapping):
            raise OperationError("invalid_prompt_import", "Prompt settings must be a JSON object.")
        _validate_known_prompt_overrides(raw)
        candidate = self.config()
        candidate["ai_prompt_config"] = dict(raw)
        registry = prompt_registry_from_config(candidate)
        candidate["ai_prompt_config"] = export_prompt_registry_overrides(registry, existing=raw)
        self._save(candidate)
        return self.list_prompt_templates()

    def preview_prompt(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        task = PromptTask(str(payload.get("task") or ""))
        values = payload.get("values", payload.get("variables"))
        if not isinstance(values, Mapping):
            raise OperationError("invalid_prompt_variables", "Prompt variables must be an object.")
        config = self.config()
        registry = prompt_registry_from_config(config)
        scope, provider_id, profile_id = _prompt_scope(payload)
        unsaved = payload.get("template")
        if unsaved is not None:
            if not isinstance(unsaved, Mapping):
                raise OperationError("invalid_prompt_template", "A prompt template object is required.")
            normalized = _snake_prompt_payload(unsaved)
            normalized["task"] = task.value
            base = default_prompt_registry().defaults[task]
            template = PromptTemplate.from_dict(normalized, variables=base.variables)
            # Register in this ephemeral registry only. Previewing must never
            # persist or silently replace the editor's unsaved text.
            if scope == "profile":
                registry.register_override(template, profile_id=profile_id)
            elif scope == "provider":
                registry.register_override(template, provider_id=provider_id)
            else:
                registry.register_default(template)
        rendered = registry.render(
            task,
            values,
            provider_id=provider_id,
            profile_id=profile_id,
        )
        preview = rendered.preview()
        built = self.request_settings(config).build(self.provider_capabilities(config), rendered)
        return {
            **preview,
            "system": rendered.system,
            "user": rendered.user,
            "effectiveSettings": built.effective_settings.to_safe_dict(),
            # Retain the nested artifact for older preview consumers.
            "preview": preview,
        }

    def get_reasoning_settings(self) -> dict[str, Any]:
        config = self.config()
        capabilities = self.provider_capabilities(config)
        return {
            "reasoning": _camelize_mapping(
                reasoning_intent_to_dict(reasoning_intent_from_config(config.get("reasoning")))
            ),
            "capabilities": _provider_capability_payload(capabilities),
        }

    def save_reasoning_settings(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        raw = payload.get("reasoning")
        if not isinstance(raw, Mapping):
            raise OperationError("invalid_reasoning", "Reasoning settings must be an object.")
        intent = _strict_reasoning_intent(raw)
        capabilities = self.provider_capabilities(self.config())
        capabilities.validate_reasoning(intent)
        config = self.config()
        config["reasoning"] = reasoning_intent_to_dict(intent)
        self._save(config)
        return self.get_reasoning_settings()

    def preview_reasoning_settings(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        raw = payload.get("reasoning")
        selected = raw if isinstance(raw, Mapping) else self.config().get("reasoning")
        intent = _strict_reasoning_intent(selected if isinstance(selected, Mapping) else {})
        capabilities = self.provider_capabilities(self.config())
        capabilities.validate_reasoning(intent)
        config = self.config()
        rendered = default_prompt_registry().render(
            PromptTask.PREPROCESSING,
            {
                "source_text": "Preview",
                "source_language": "",
                "custom_instructions": "Preview request settings only.",
            },
        )
        current = self.request_settings(config)
        settings = ModelRequestSettings(
            model=current.model,
            max_output_tokens=current.max_output_tokens,
            temperature=current.temperature,
            top_p=current.top_p,
            reasoning=intent,
            use_native_structured_output=current.use_native_structured_output,
            extra_body=current.extra_body,
        )
        built = settings.build(capabilities, rendered)
        return {
            "reasoning": _camelize_mapping(reasoning_intent_to_dict(intent)),
            "capabilities": _provider_capability_payload(capabilities),
            "effectiveSettings": built.effective_settings.to_safe_dict(),
        }

    # Target-aware generation ----------------------------------------

    def generate_target_aware(
        self,
        payload: Mapping[str, Any],
        context: OperationContext,
    ) -> dict[str, Any]:
        config = self.config()
        targets = []
        for row in payload.get("targets") or []:
            if not isinstance(row, Mapping):
                continue
            targets.append(GenerationTarget(
                str(row.get("id") or ""),
                str(row.get("text") or ""),
                TargetCategory(str(row.get("category") or "optional")),
                tuple(str(value) for value in row.get("equivalentForms") or []),
            ))
        request = ArticleGenerationRequest(
            str(payload.get("targetLanguage") or ""),
            tuple(targets),
            source_text=str(payload.get("sourceText") or ""),
            source_language=str(payload.get("sourceLanguage") or ""),
            proficiency_level=str(payload.get("proficiencyLevel") or ""),
            genre=str(payload.get("genre") or ""),
            desired_length=str(payload.get("desiredLength") or ""),
            style=str(payload.get("style") or ""),
            custom_instructions=str(payload.get("customInstructions") or ""),
        )
        result = generate_target_aware_article(
            request,
            registry=prompt_registry_from_config(config),
            provider_capabilities=self.provider_capabilities(config),
            request_settings=self.request_settings(config),
            transport=OpenAICompatibleTransport(config),
            context=context,
            provider_id=str(config.get("selected_provider_profile") or ""),
            profile_id=str(config.get("selected_llm_api_profile_id") or ""),
        )
        return result.to_dict()

    # Shared settings helpers ----------------------------------------

    def config(self) -> dict[str, Any]:
        return normalize_config(self._load())

    def provider_capabilities(self, config: Mapping[str, Any]):
        return known_provider_capabilities(str(config.get("selected_provider_profile") or "custom"))

    def request_settings(self, config: Mapping[str, Any]) -> ModelRequestSettings:
        return ModelRequestSettings(
            model=str(config.get("model") or ""),
            max_output_tokens=int(config.get("max_tokens") or 30000),
            temperature=float(config["temperature"]) if config.get("temperature") is not None else None,
            top_p=float(config["top_p"]) if config.get("top_p") is not None else None,
            reasoning=reasoning_intent_from_config(config.get("reasoning")),
            use_native_structured_output=bool(config.get("use_native_structured_output", False)),
            extra_body=dict(config.get("extra_body") or {}) if isinstance(config.get("extra_body"), Mapping) else {},
        )

    def _selected_preset(self, preset_id: str | None) -> ScoringPreset:
        config = self.config()
        selected = preset_id or str(config.get("selected_scoring_preset_id") or "")
        for raw in config.get("scoring_presets") or []:
            if raw.get("id") == selected:
                return ScoringPreset.from_dict(raw)
        return recommended_preset()

    def _article_reference_path(self, value: Any) -> str:
        text = str(value or "").strip()
        path = Path(text)
        if not path.is_absolute():
            return text.replace("\\", "/")
        article_root = (self.history_root / "articles").resolve()
        try:
            return path.resolve(strict=False).relative_to(article_root).as_posix()
        except ValueError as exc:
            raise OperationError(
                "invalid_article_reference",
                "The selected article is outside DAIRR article history.",
            ) from exc

    def _load_session(self, session_id: str):
        with self._session_lock:
            session = self._sessions.get(session_id)
        if session is not None:
            return session
        session = self.practice.load_session(session_id)
        self._remember_session(session)
        return session

    def _remember_session(self, session: Any, *, increment_revision: bool = False) -> None:
        with self._session_lock:
            self._sessions[session.id] = session
            current = self._revisions.get(session.id, 0)
            self._revisions[session.id] = current + 1 if increment_revision else current

    def _check_revision(self, session_id: str, payload: Mapping[str, Any]) -> None:
        if payload.get("revision") is None:
            return
        try:
            supplied = int(payload["revision"])
        except (TypeError, ValueError) as exc:
            raise OperationError("invalid_revision", "The practice revision is invalid.") from exc
        with self._session_lock:
            current = self._revisions.get(session_id, 0)
        if supplied != current:
            raise OperationError(
                "stale_practice_revision",
                "This practice session changed in another operation. Reload it before saving.",
                retryable=True,
            )

    def _session_payload(self, session: Any) -> dict[str, Any]:
        with self._session_lock:
            revision = self._revisions.get(session.id, 0)
        payload = _session_payload(session)
        payload["revision"] = revision
        return payload

    @staticmethod
    def _template_payload(template: PromptTemplate) -> dict[str, Any]:
        result = _camelize_mapping(template.to_dict())
        result["variables"] = [
            {"name": item.name, "description": item.description, "required": item.required}
            for item in template.documented_variables
        ]
        return result


def _session_payload(session: Any) -> dict[str, Any]:
    return _camelize_mapping(session_document(session)["session"])


def _article_practice_material(
    raw_article: str,
    direction: TranslationDirection,
) -> tuple[str, list[str | None], str]:
    parsed = parse_article_response(raw_article)
    pairs: list[tuple[str, str | None]] = []
    paragraph: list[str] = []
    for line in str(parsed.get("main_article") or "").splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("[t]"):
            translation = stripped[3:].strip()
            if paragraph:
                pairs.append(("\n".join(paragraph).strip(), translation or None))
                paragraph = []
            elif pairs:
                previous, _old = pairs[-1]
                pairs[-1] = (previous, translation or None)
        elif not stripped:
            if paragraph:
                pairs.append(("\n".join(paragraph).strip(), None))
                paragraph = []
        else:
            paragraph.append(line)
    if paragraph:
        pairs.append(("\n".join(paragraph).strip(), None))
    pairs = [(source, reference) for source, reference in pairs if source]
    if not pairs:
        main = str(parsed.get("main_article") or raw_article).strip()
        return main, [None] if main else [], str(parsed.get("title") or "")
    if direction is TranslationDirection.BACK_TRANSLATION and any(
        reference for _source, reference in pairs
    ):
        sources = [reference if reference else source for source, reference in pairs]
        references = [source if reference else None for source, reference in pairs]
    else:
        sources = [source for source, _reference in pairs]
        references = [reference for _source, reference in pairs]
    return "\n\n".join(sources), references, str(parsed.get("title") or "")


def _direction(value: Any, *, article: bool = False) -> TranslationDirection:
    default = "back_translation" if article else "source_to_target"
    try:
        return TranslationDirection(str(value or default))
    except ValueError as exc:
        raise OperationError("invalid_direction", "The selected translation direction is invalid.") from exc


def _required_id(payload: Mapping[str, Any], key: str) -> str:
    value = str(payload.get(key) or "").strip()
    if not value:
        raise OperationError("missing_identifier", "A required identifier is missing.")
    return value


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _camelize_mapping(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            _CAMEL_BOUNDARY.sub(lambda match: match.group(1).upper(), str(key)): _camelize_mapping(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_camelize_mapping(item) for item in value]
    return _json_value(value)


def _json_value(value: Any) -> Any:
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return _camelize_mapping(value.to_dict())
    if hasattr(value, "__dataclass_fields__"):
        return {
            _CAMEL_BOUNDARY.sub(lambda match: match.group(1).upper(), name): _json_value(getattr(value, name))
            for name in value.__dataclass_fields__
        }
    if hasattr(value, "value") and isinstance(getattr(value, "value"), (str, int, float, bool)):
        return value.value
    if isinstance(value, Mapping):
        return _camelize_mapping(value)
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _snake_prompt_payload(value: Mapping[str, Any]) -> dict[str, Any]:
    aliases = {
        "systemTemplate": "system_template",
        "userTemplate": "user_template",
        "responseMode": "response_mode",
        "responseContract": "response_contract",
    }
    return {aliases.get(str(key), str(key)): item for key, item in value.items()}


def _prompt_scope(payload: Mapping[str, Any]) -> tuple[str, str, str]:
    scope = str(payload.get("scope") or "task")
    provider_id = str(payload.get("providerId") or "").strip()
    profile_id = str(payload.get("profileId") or "").strip()
    if scope == "provider" and not provider_id:
        raise OperationError("missing_provider", "Choose a provider for this prompt override.")
    if scope == "profile" and not profile_id:
        raise OperationError("missing_profile", "Choose a profile for this prompt override.")
    if scope not in {"task", "provider", "profile"}:
        raise OperationError("invalid_prompt_scope", "The prompt override scope is invalid.")
    return scope, provider_id, profile_id


def _provider_capability_payload(capabilities: Any) -> dict[str, Any]:
    return {
        "supportsReasoning": capabilities.supports_reasoning,
        "controls": sorted(value.value for value in capabilities.reasoning_controls),
        "effortLevels": list(capabilities.effort_levels),
        "minimumBudgetTokens": capabilities.minimum_budget_tokens,
        "maximumBudgetTokens": capabilities.maximum_budget_tokens,
    }


def _strict_reasoning_intent(raw: Mapping[str, Any]) -> ReasoningIntent:
    try:
        mode = ReasoningMode(str(raw.get("mode") or "provider_default"))
        control_value = raw.get("control")
        control = ReasoningControl(str(control_value)) if control_value else None
        effort = str(raw["effort"]) if raw.get("effort") is not None else None
        budget_value = raw.get("budget_tokens", raw.get("budgetTokens"))
        budget = int(budget_value) if budget_value is not None else None
        return ReasoningIntent(mode, control, effort, budget)
    except (ValueError, TypeError, ProviderConfigurationError) as exc:
        raise OperationError("invalid_reasoning", "The selected reasoning settings are invalid.") from exc


def _validate_known_prompt_overrides(raw: Mapping[str, Any]) -> None:
    defaults = default_prompt_registry().defaults

    def validate_tasks(tasks: Any) -> None:
        if not isinstance(tasks, Mapping):
            raise OperationError("invalid_prompt_import", "Prompt override groups must be objects.")
        for task_name, payload in tasks.items():
            try:
                task = PromptTask(str(task_name))
            except ValueError:
                # Preserve forward-compatible tasks for a newer release.
                continue
            if not isinstance(payload, Mapping):
                raise OperationError("invalid_prompt_import", "Prompt templates must be objects.")
            normalized = _snake_prompt_payload(payload)
            normalized["task"] = task.value
            try:
                PromptTemplate.from_dict(normalized, variables=defaults[task].variables)
            except Exception as exc:
                raise OperationError(
                    "invalid_prompt_import",
                    f"The {task.value} prompt template is invalid.",
                ) from exc

    validate_tasks(raw.get("task_overrides") or {})
    for group_name in ("provider_overrides", "profile_overrides"):
        groups = raw.get(group_name) or {}
        if not isinstance(groups, Mapping):
            raise OperationError("invalid_prompt_import", "Prompt override scopes must be objects.")
        for tasks in groups.values():
            validate_tasks(tasks)
