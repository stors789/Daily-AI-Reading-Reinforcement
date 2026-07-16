"""Static contract checks for the portable next-major-release workbench.

These tests intentionally check the UI/service boundary instead of duplicating
domain behavior that is covered in dairr_core.  Both the desktop host and the
Anki add-on inline these same three assets.
"""

from __future__ import annotations

import re
import unittest
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).parents[1]
WEB = ROOT / "addon" / "daily_ai_reading_reinforcement" / "web"
INDEX = WEB / "index.html"
APP = WEB / "app.js"
STYLE = WEB / "style.css"


class _IdParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()

    def handle_starttag(self, _tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if name == "id" and value:
                self.ids.add(value)


class ReleaseWorkbenchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.html = INDEX.read_text(encoding="utf-8")
        cls.js = APP.read_text(encoding="utf-8")
        cls.css = STYLE.read_text(encoding="utf-8")

    def test_navigation_exposes_every_release_workspace(self) -> None:
        for view in (
            "generate",
            "practice",
            "articles",
            "practice-history",
            "scoring",
            "prompts",
            "api",
        ):
            with self.subTest(view=view):
                self.assertIn(f'data-view="{view}"', self.html)
        for panel in ("generate", "practice", "practice-history", "scoring", "prompts", "api"):
            self.assertIn(f'data-view-panel="{panel}"', self.html)

    def test_practice_surface_has_both_entry_paths_and_editing_controls(self) -> None:
        for required in (
            'data-practice-kind="pasted_text"',
            'data-practice-kind="article"',
            'data-practice-scope="segment"',
            'data-practice-scope="complete_text"',
            'id="splitSegmentButton"',
            'id="mergeSegmentButton"',
            'id="moveSegmentUpButton"',
            'id="moveSegmentDownButton"',
            'id="revealReferenceButton"',
            'id="practiceAttempts"',
            'id="cancelPracticeOperationButton"',
        ):
            self.assertIn(required, self.html)

    def test_practice_drafts_have_explicit_limit_recovery_and_revision_guard(self) -> None:
        self.assertIn("MAX_PASTED_CHARACTERS = 50000", self.js)
        self.assertIn("Text exceeds the ${limit.toLocaleString()} character limit and was not sent.", self.js)
        self.assertIn("practiceStorageKey", self.js)
        self.assertIn('window.addEventListener("beforeunload"', self.js)
        self.assertIn("revision: session.revision", self.js)
        self.assertIn('sendV2("savePracticeDraft"', self.js)
        self.assertNotIn('maxlength="50000"', self.html)
        self.assertIn("draftSaveInFlight", self.js)
        self.assertIn("queuedDraftSave", self.js)
        self.assertIn("flushPracticeMutationQueue", self.js)
        self.assertIn("pendingDraftSaves", self.js)
        self.assertIn("sourceText: local.sourceText", self.js)
        self.assertIn("handlePracticeMutationFailure", self.js)
        self.assertIn("Your local draft is safe; reopen the session", self.js)
        self.assertNotIn("console.log(sourceText", self.js)
        self.assertNotIn("console.log(translation", self.js)

    def test_versioned_bridge_covers_release_service_families(self) -> None:
        self.assertIn("const BRIDGE_VERSION = 2", self.js)
        self.assertIn("requestId: id", self.js)
        self.assertIn("releaseState.latestRequests", self.js)
        self.assertIn("function isCurrent(message)", self.js)
        for action in (
            "getCapabilities",
            "createPastedPractice",
            "createArticlePractice",
            "listPracticeSessions",
            "loadPracticeSession",
            "savePracticeDraft",
            "updatePracticeSegments",
            "submitPracticeReview",
            "cancelOperation",
            "getScoringConfig",
            "saveScoringConfig",
            "resetScoringConfig",
            "importScoringConfig",
            "exportScoringConfig",
            "previewScoring",
            "generateTargetAware",
            "getPromptTemplate",
            "savePromptTemplate",
            "resetPromptTemplate",
            "importPromptTemplates",
            "exportPromptTemplates",
            "previewPrompt",
            "getReasoningSettings",
            "saveReasoningSettings",
            "previewReasoningSettings",
        ):
            with self.subTest(action=action):
                self.assertIn(f'"{action}"', self.js)

    def test_async_terminal_events_are_scoped_to_request_and_session_currency(self) -> None:
        self.assertIn("practiceSessionEpoch", self.js)
        self.assertIn("function operationIsCurrent(operationId)", self.js)
        self.assertIn("releaseState.latestRequests.get(meta.channel) !== meta.requestId", self.js)
        self.assertIn("meta.sessionEpoch !== releaseState.practiceSessionEpoch", self.js)
        self.assertIn("if (!operationIsCurrent(operationId))", self.js)
        self.assertIn("revisionOfSessionId", self.js)
        self.assertIn("releaseState.revisionOfSessionId === session.id", self.js)

    def test_scoring_ui_exposes_transparency_and_manual_categories(self) -> None:
        for text in (
            "Simple",
            "Advanced",
            "Minimum inclusion score",
            "Maximum selected cards",
            "Score normalization",
            "Preview candidates",
            "Required",
            "Preferred",
            "Optional",
            "Excluded",
        ):
            self.assertIn(text, self.html + self.js)
        self.assertIn("item.status === \"unavailable\"", self.js)
        self.assertIn("item.contribution", self.js)
        self.assertIn('id="useTargetPlanButton"', self.html)
        self.assertIn("releaseState.targetPlanActive", self.js)
        self.assertIn('sendV2("generateTargetAware"', self.js)
        for role in (
            "normalizeBy",
            "minimumContribution",
            "maximumContribution",
            "decayEnabled",
            "halfLifeDays",
        ):
            self.assertIn(f'data-role="{role}"', self.js)
            self.assertIn(f'rule.{role}' if role not in {"decayEnabled", "halfLifeDays"} else "rule.decay", self.js)
        self.assertIn("scoringSortDescending", self.js)
        self.assertIn('sortCandidatesButton").addEventListener', self.js)

    def test_prompt_ui_shows_editable_contract_and_exact_preview(self) -> None:
        for element_id in (
            "promptTask",
            "promptOverrideScope",
            "promptResponseMode",
            "promptSystemTemplate",
            "promptUserTemplate",
            "promptResponseContract",
            "renderedPromptMessages",
            "renderedPromptContract",
            "promptEffectiveSettings",
        ):
            self.assertIn(f'id="{element_id}"', self.html)
        self.assertIn("template: templatePayload()", self.js)
        self.assertIn("missingVariables", self.js)
        self.assertIn('id="promptValueFields"', self.html)
        self.assertIn('id="previewPracticePromptButton"', self.html)
        self.assertIn('class="form-field mandatory-contract"', self.html)
        self.assertIn("currentPendingPromptValues", self.js)
        self.assertIn("promptPreviewValuePayload", self.js)

    def test_reasoning_modes_remain_semantically_distinct(self) -> None:
        for mode in ("disabled", "provider_default", "explicit"):
            self.assertIn(f'value="{mode}"', self.html)
        self.assertIn('if (mode !== "explicit") return { mode, control: null, effort: null, budgetTokens: null }', self.js)
        self.assertIn("supportsReasoning", self.js)
        self.assertIn("effectiveSettings", self.js)
        self.assertIn("minimumBudgetTokens", self.js)
        self.assertIn("maximumBudgetTokens", self.js)
        self.assertIn("validateReasoning", self.js)
        self.assertIn('(caps.controls || []).includes(intent.control)', self.js)

    def test_review_history_complete_reference_and_capability_failures_are_visible(self) -> None:
        self.assertIn('class="attempt-review"', self.js)
        self.assertIn("reviewed.review", self.js)
        self.assertIn("completeReference", self.js)
        self.assertIn('id="capabilityDetails"', self.html)
        self.assertIn("setCapabilityAction", self.js)
        self.assertIn('setCapabilityAction("submitPracticeButton", "custom_prompts"', self.js)

    def test_signature_segment_rail_encodes_real_practice_state(self) -> None:
        self.assertIn(".segment-rail::before", self.css)
        self.assertIn(".segment-marker.has-draft", self.css)
        self.assertIn(".segment-marker.reviewed", self.css)
        self.assertIn(".segment-marker.active", self.css)
        self.assertIn('classes.push("has-draft")', self.js)
        self.assertIn('classes.push("reviewed")', self.js)

    def test_accessibility_and_motion_baseline_is_present(self) -> None:
        self.assertIn(":focus-visible", self.css)
        self.assertIn("@media (prefers-reduced-motion: reduce)", self.css)
        self.assertIn('aria-live="polite"', self.html)
        self.assertIn('aria-label="Practice segments"', self.html)
        self.assertIn('aria-expanded="false"', self.html)
        self.assertIn('role="alert"', self.html)
        self.assertIn('aria-pressed="true"', self.html)
        self.assertIn("reducedMotion() ? \"auto\" : \"smooth\"", self.js)

    def test_workbench_static_copy_has_zh_en_ja_localization_path(self) -> None:
        self.assertIn("const WORKBENCH_COPY", self.js)
        self.assertIn("function applyWorkbenchCopy", self.js)
        self.assertIn('zh: {', self.js)
        self.assertIn('ja: {', self.js)
        self.assertIn("MutationObserver", self.js)

    def test_new_javascript_id_references_exist_in_shared_markup(self) -> None:
        parser = _IdParser()
        parser.feed(self.html)
        release_block = self.js[self.js.index("(function initReleaseWorkbench()") :]
        referenced = set(re.findall(r'\$\("([A-Za-z][A-Za-z0-9_-]*)"\)', release_block))
        missing = sorted(referenced - parser.ids)
        self.assertEqual(missing, [], f"release JS references missing elements: {missing}")


if __name__ == "__main__":
    unittest.main()
