from __future__ import annotations

import sys
import unittest
from pathlib import Path


CORE_SRC = Path(__file__).resolve().parent.parent / "packages" / "dairr_core" / "src"
if str(CORE_SRC) not in sys.path:
    sys.path.insert(0, str(CORE_SRC))

from dairr_core.prompt_templates import PromptTask, ResponseMode, default_prompt_registry
from dairr_core.response_parsing import ResponseParseError, parse_model_response
from dairr_core.translation_review import (
    TranslationReviewRequest,
    parse_translation_review,
    render_translation_review_prompt,
)


class TranslationReviewTests(unittest.TestCase):
    def test_no_reference_selects_direct_review_and_forbids_invented_canonical_answer(self) -> None:
        request = TranslationReviewRequest("Hello", "Hola", "English", "Spanish")
        rendered = render_translation_review_prompt(default_prompt_registry(), request)
        self.assertIs(rendered.task, PromptTask.TRANSLATION_REVIEW)
        self.assertIn("There is no authoritative reference translation", rendered.user)
        self.assertNotIn("Reference translation:\n", rendered.user)

    def test_reference_selects_back_translation_as_comparison_only(self) -> None:
        request = TranslationReviewRequest(
            "Hello", "Hola", "English", "Spanish", reference_translation="Buenas"
        )
        rendered = render_translation_review_prompt(default_prompt_registry(), request)
        self.assertIs(rendered.task, PromptTask.BACK_TRANSLATION_REVIEW)
        self.assertIn("Reference translation:\nBuenas", rendered.user)
        self.assertIn("not the only valid answer", rendered.system)

    def test_custom_instructions_and_multiline_private_text_are_rendered_exactly(self) -> None:
        request = TranslationReviewRequest(
            "diary\nentry", "日記\nです", "English", "Japanese",
            proficiency_level="N3", custom_instructions="Focus on tone.\nBe concise.",
        )
        rendered = render_translation_review_prompt(default_prompt_registry(), request)
        self.assertIn("diary\nentry", rendered.user)
        self.assertIn("日記\nです", rendered.user)
        self.assertIn("Focus on tone.\nBe concise.", rendered.user)

    def test_plain_text_review_requires_no_structured_parser(self) -> None:
        result = parse_translation_review(
            "Useful free-form feedback.",
            mode=ResponseMode.PLAIN_TEXT,
            reference_was_provided=False,
        )
        self.assertEqual(result.plain_text, "Useful free-form feedback.")
        self.assertEqual(result.categories, {})

    def test_structured_review_accepts_strings_lists_and_nested_categories(self) -> None:
        raw = """{
          "meaning": ["One mistranslation", "One ambiguity"],
          "grammar": "Fix agreement.",
          "vocabulary": {"collocation": "Use make a decision."},
          "suggested_revision": "Improved text",
          "overall": "Good foundation"
        }"""
        result = parse_translation_review(
            raw,
            mode=ResponseMode.STRUCTURED,
            reference_was_provided=False,
        )
        self.assertEqual(result.categories["meaning"], ("One mistranslation", "One ambiguity"))
        self.assertEqual(result.categories["grammar"], ("Fix agreement.",))
        self.assertEqual(result.categories["vocabulary"], ("collocation: Use make a decision.",))
        self.assertEqual(result.suggested_revision, "Improved text")

    def test_fences_wrapper_prose_and_envelope_are_recovered(self) -> None:
        fenced = parse_model_response('```json\n{"meaning":"ok"}\n```', ResponseMode.STRUCTURED)
        self.assertEqual(fenced.data, {"meaning": "ok"})
        self.assertTrue(fenced.warnings)

        wrapped = parse_model_response(
            'Provider preface {"review":{"naturalness":"awkward"}} thanks',
            ResponseMode.STRUCTURED,
        )
        self.assertEqual(wrapped.data, {"naturalness": "awkward"})
        self.assertTrue(wrapped.recovered_from_wrapper)

    def test_duplicate_fields_use_final_value_with_warning(self) -> None:
        parsed = parse_translation_review(
            '{"grammar":"first","grammar":"second"}',
            mode=ResponseMode.STRUCTURED,
            reference_was_provided=False,
        )
        self.assertEqual(parsed.categories["grammar"], ("second",))
        self.assertTrue(any("Duplicate" in warning for warning in parsed.warnings))

    def test_partial_structured_review_is_useful(self) -> None:
        parsed = parse_translation_review(
            '{"naturalness":"Understandable but stiff."}',
            mode=ResponseMode.STRUCTURED,
            reference_was_provided=False,
        )
        self.assertEqual(parsed.categories, {"naturalness": ("Understandable but stiff.",)})

    def test_unknown_fields_are_ignored_with_explanation(self) -> None:
        parsed = parse_translation_review(
            '{"meaning":"Accurate","score":99}',
            mode=ResponseMode.STRUCTURED,
            reference_was_provided=False,
        )
        self.assertTrue(any("score" in warning for warning in parsed.warnings))

    def test_no_reference_claim_from_model_is_not_trusted(self) -> None:
        parsed = parse_translation_review(
            '{"meaning":"Accurate","reference_used":true}',
            mode=ResponseMode.STRUCTURED,
            reference_was_provided=False,
        )
        self.assertFalse(parsed.reference_used)
        self.assertTrue(any("Ignored a model claim" in warning for warning in parsed.warnings))

    def test_malformed_and_empty_recognized_feedback_are_safe_errors(self) -> None:
        with self.assertRaises(ResponseParseError) as malformed:
            parse_translation_review(
                "not json", mode=ResponseMode.STRUCTURED, reference_was_provided=False
            )
        self.assertEqual(malformed.exception.code, "invalid_json")
        self.assertNotIn("not json", str(malformed.exception))

        with self.assertRaises(ResponseParseError) as empty:
            parse_translation_review(
                '{"score": 100}', mode=ResponseMode.STRUCTURED, reference_was_provided=False
            )
        self.assertEqual(empty.exception.code, "empty_review")

    def test_truncation_is_distinguished_from_generic_invalid_json(self) -> None:
        with self.assertRaises(ResponseParseError) as raised:
            parse_translation_review(
                '{"meaning":"cut off',
                mode=ResponseMode.STRUCTURED,
                reference_was_provided=False,
                finish_reason="length",
            )
        self.assertEqual(raised.exception.code, "truncated_json")
        self.assertTrue(raised.exception.possibly_truncated)

    def test_complete_response_can_still_carry_provider_length_warning(self) -> None:
        parsed = parse_translation_review(
            '{"overall":"Partial but valid"}',
            mode=ResponseMode.STRUCTURED,
            reference_was_provided=True,
            finish_reason="length",
        )
        self.assertTrue(parsed.possibly_truncated)
        self.assertTrue(parsed.reference_used)


if __name__ == "__main__":
    unittest.main()
