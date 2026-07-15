from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


CORE_SRC = Path(__file__).resolve().parent.parent / "packages" / "dairr_core" / "src"
if str(CORE_SRC) not in sys.path:
    sys.path.insert(0, str(CORE_SRC))

from dairr_core.article_generation import (
    ArticleGenerationRequest,
    GenerationTarget,
    TargetOutcomeStatus,
    generate_target_aware_article,
    parse_article_generation_response,
    prepare_article_generation,
)
from dairr_core.operations import ModelRequestSettings, ModelResponse, OperationContext
from dairr_core.prompt_templates import ResponseMode, default_prompt_registry
from dairr_core.provider_capabilities import known_provider_capabilities
from dairr_core.response_parsing import ResponseParseError
from dairr_core.target_selection import TargetCategory


def targets():
    return (
        GenerationTarget("r", "make a decision", TargetCategory.REQUIRED),
        GenerationTarget("p", "went", TargetCategory.PREFERRED, ("go",)),
        GenerationTarget("o", "optional phrase", TargetCategory.OPTIONAL),
        GenerationTarget("x", "forbidden phrase", TargetCategory.EXCLUDED),
    )


def request():
    return ArticleGenerationRequest(
        "English",
        targets(),
        source_text="card context",
        source_language="Japanese",
        proficiency_level="B1",
        genre="essay",
        desired_length="300 words",
        style="reflective",
        custom_instructions="Keep it grounded.",
    )


class FakeTransport:
    def __init__(self, content, finish_reason=None):
        self.response = ModelResponse(content, finish_reason)
        self.request = None

    def complete(self, request, *, cancellation):
        self.request = request
        return self.response


class ArticleGenerationServiceTests(unittest.TestCase):
    def test_prepare_renders_all_categories_style_and_exact_provider_messages(self) -> None:
        prepared = prepare_article_generation(
            request(),
            registry=default_prompt_registry(),
            provider_capabilities=known_provider_capabilities("openrouter"),
            request_settings=ModelRequestSettings("model"),
            context=OperationContext(),
        )
        self.assertIn('"category":"required"', prepared.prompt.user)
        self.assertIn('"category":"preferred"', prepared.prompt.user)
        self.assertIn('"category":"optional"', prepared.prompt.user)
        self.assertIn('"category":"excluded"', prepared.prompt.user)
        self.assertIn("Requested style: reflective", prepared.prompt.user)
        self.assertEqual(prepared.provider_request.body["messages"], list(prepared.prompt.messages))

    def test_structured_response_tracks_exact_inflected_unusable_and_unreported(self) -> None:
        raw = json.dumps({
            "title": "A Choice",
            "article": "I made a decision and then went home.",
            "paragraph_translations": ["translation"],
            "target_usage": [
                {"target_id": "r", "actual_surface_form": "make a decision", "status": "exact"},
                {"target_id": "p", "actual_surface_form": "went", "status": "inflected"},
            ],
            "unused_targets": [{"target_id": "o", "reason": "Would be unnatural."}],
        })
        result = parse_article_generation_response(request(), raw, mode=ResponseMode.STRUCTURED)
        outcomes = {item.target_id: item for item in result.target_outcomes}
        self.assertIs(outcomes["r"].status, TargetOutcomeStatus.EXACT)
        self.assertIs(outcomes["p"].status, TargetOutcomeStatus.INFLECTED)
        self.assertIs(outcomes["o"].status, TargetOutcomeStatus.UNUSABLE)
        self.assertIs(outcomes["x"].status, TargetOutcomeStatus.EXCLUDED)
        self.assertEqual(result.paragraph_translations, ("translation",))

    def test_equivalent_form_is_recognized_without_literal_reproduction(self) -> None:
        raw = '{"title":"T","article":"They go.","target_usage":[' \
              '{"target_id":"p","actual_surface_form":"go"}]}'
        result = parse_article_generation_response(request(), raw, mode=ResponseMode.STRUCTURED)
        outcome = next(item for item in result.target_outcomes if item.target_id == "p")
        self.assertIs(outcome.status, TargetOutcomeStatus.EQUIVALENT)

    def test_optional_target_can_be_omitted_without_priority_warning(self) -> None:
        req = ArticleGenerationRequest(
            "English", (GenerationTarget("o", "maybe", TargetCategory.OPTIONAL),)
        )
        result = parse_article_generation_response(
            req, '{"article":"A coherent article."}', mode=ResponseMode.STRUCTURED
        )
        self.assertFalse(any("required or preferred" in warning for warning in result.warnings))
        self.assertIs(result.target_outcomes[0].status, TargetOutcomeStatus.UNREPORTED)

    def test_required_missing_mapping_is_explicit_but_article_remains_usable(self) -> None:
        result = parse_article_generation_response(
            request(), '{"article":"A partial but useful result."}', mode=ResponseMode.STRUCTURED
        )
        self.assertTrue(any("required or preferred" in warning for warning in result.warnings))
        self.assertEqual(result.article, "A partial but useful result.")

    def test_fence_provider_wrapper_and_envelope_are_recovered(self) -> None:
        raw = 'Provider says ```json\n{"response":{"title":"T","article":"Body"}}\n``` thanks'
        # A fence embedded in prose is recovered by object scanning, then the envelope is removed.
        result = parse_article_generation_response(request(), raw, mode=ResponseMode.STRUCTURED)
        self.assertEqual(result.article, "Body")
        self.assertTrue(result.recovered)

    def test_duplicate_json_fields_use_last_value_and_warn(self) -> None:
        result = parse_article_generation_response(
            request(),
            '{"article":"old","article":"new"}',
            mode=ResponseMode.STRUCTURED,
        )
        self.assertEqual(result.article, "new")
        self.assertTrue(any("Duplicate JSON" in warning for warning in result.warnings))

    def test_duplicate_target_mappings_merge_surface_forms(self) -> None:
        raw = json.dumps({
            "article": "Body",
            "target_usage": [
                {"target_id": "r", "actual_surface_form": "made a decision"},
                {"target_id": "r", "actual_surface_form": "make a decision"},
            ],
        })
        result = parse_article_generation_response(request(), raw, mode=ResponseMode.STRUCTURED)
        outcome = next(item for item in result.target_outcomes if item.target_id == "r")
        self.assertEqual(outcome.actual_surface_forms, ("made a decision", "make a decision"))
        self.assertTrue(any("duplicate" in warning for warning in result.warnings))

    def test_unexpected_and_malformed_mappings_are_ignored_without_echoing_content(self) -> None:
        raw = json.dumps({
            "article": "Body",
            "target_usage": [
                {"target": "PRIVATE UNKNOWN TARGET", "actual": "SECRET"},
                42,
            ],
            "private_unknown_field": "PRIVATE VALUE",
        })
        result = parse_article_generation_response(request(), raw, mode=ResponseMode.STRUCTURED)
        warning_text = " ".join(result.warnings)
        self.assertIn("unexpected target", warning_text)
        self.assertIn("malformed target", warning_text)
        self.assertNotIn("PRIVATE", warning_text)
        self.assertNotIn("SECRET", warning_text)

    def test_excluded_usage_is_a_machine_readable_violation(self) -> None:
        raw = '{"article":"Body","target_usage":[{"target_id":"x","actual":"forbidden phrase"}]}'
        result = parse_article_generation_response(request(), raw, mode=ResponseMode.STRUCTURED)
        outcome = next(item for item in result.target_outcomes if item.target_id == "x")
        self.assertIs(outcome.status, TargetOutcomeStatus.EXCLUDED_VIOLATION)
        self.assertTrue(any("violation" in warning for warning in result.warnings))

    def test_plain_text_mode_returns_article_and_honest_unreported_usage(self) -> None:
        result = parse_article_generation_response(
            request(), "Plain article text.", mode=ResponseMode.PLAIN_TEXT, finish_reason="length"
        )
        self.assertEqual(result.article, "Plain article text.")
        self.assertTrue(result.possibly_truncated)
        self.assertTrue(all(
            item.status in {TargetOutcomeStatus.UNREPORTED, TargetOutcomeStatus.EXCLUDED}
            for item in result.target_outcomes
        ))

    def test_complete_article_field_recovers_from_truncated_later_json(self) -> None:
        raw = '{"title":"Recovered","article":"Complete body","target_usage":[{"target_id":"r"'
        result = parse_article_generation_response(
            request(), raw, mode=ResponseMode.STRUCTURED, finish_reason="length"
        )
        self.assertEqual(result.article, "Complete body")
        self.assertTrue(result.recovered)
        self.assertTrue(result.possibly_truncated)

    def test_malformed_response_without_complete_article_is_safe_error(self) -> None:
        private = 'PRIVATE_DIARY {"article":"cut off'
        with self.assertRaises(ResponseParseError) as raised:
            parse_article_generation_response(request(), private, mode=ResponseMode.STRUCTURED)
        self.assertNotIn("PRIVATE_DIARY", str(raised.exception))
        self.assertTrue(raised.exception.possibly_truncated)

    def test_mapping_response_and_alternate_fields_are_tolerated(self) -> None:
        result = parse_article_generation_response(
            request(),
            {"article_title": "Alt", "content": "Body", "translations": [{"text": "T"}]},
            mode=ResponseMode.STRUCTURED,
        )
        self.assertEqual((result.title, result.article, result.paragraph_translations), ("Alt", "Body", ("T",)))

    def test_end_to_end_generation_pipeline_uses_transport_and_parses_result(self) -> None:
        transport = FakeTransport('{"title":"T","article":"Body","unused_targets":["optional phrase"]}')
        result = generate_target_aware_article(
            request(),
            registry=default_prompt_registry(),
            provider_capabilities=known_provider_capabilities("custom"),
            request_settings=ModelRequestSettings("fake-model"),
            transport=transport,
            context=OperationContext(),
        )
        self.assertEqual(result.article, "Body")
        self.assertEqual(transport.request.body["model"], "fake-model")

    def test_missing_article_and_invalid_response_type_are_rejected(self) -> None:
        for raw in ('{"title":"Only title"}', 42):
            with self.subTest(raw=raw), self.assertRaises(ResponseParseError):
                parse_article_generation_response(request(), raw, mode=ResponseMode.STRUCTURED)


if __name__ == "__main__":
    unittest.main()
