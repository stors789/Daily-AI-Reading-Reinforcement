from __future__ import annotations

import sys
import unittest
from pathlib import Path


CORE_SRC = Path(__file__).resolve().parent.parent / "packages" / "dairr_core" / "src"
if str(CORE_SRC) not in sys.path:
    sys.path.insert(0, str(CORE_SRC))

from dairr_core.prompt_templates import (
    PromptRegistry,
    PromptTask,
    PromptTemplate,
    PromptTemplateError,
    ResponseMode,
    VariableSpec,
    default_prompt_registry,
    render_prompt,
)


class PromptTemplateTests(unittest.TestCase):
    def test_registry_contains_every_required_workflow(self) -> None:
        registry = default_prompt_registry()
        self.assertEqual(set(registry.defaults), set(PromptTask))

    def test_rendered_preview_is_exact_messages_without_hidden_suffix(self) -> None:
        template = PromptTemplate(
            PromptTask.PREPROCESSING,
            "My system {language}",
            "My user\n{text}",
            ResponseMode.PLAIN_TEXT,
            variables=(VariableSpec("language", "Language"), VariableSpec("text", "Text")),
        )
        rendered = render_prompt(template, {"language": "Japanese", "text": "line 1\nline 2"})
        self.assertEqual(
            rendered.preview()["messages"],
            [
                {"role": "system", "content": "My system Japanese"},
                {"role": "user", "content": "My user\nline 1\nline 2"},
            ],
        )
        self.assertEqual(rendered.messages, tuple(rendered.preview()["messages"]))

    def test_multiline_custom_prompt_is_preserved(self) -> None:
        default = default_prompt_registry().resolve(PromptTask.PREPROCESSING)
        custom = default.with_custom_text(
            system_template="first\nsecond",
            user_template="before\n{source_text}\nafter",
        )
        rendered = render_prompt(
            custom,
            {"source_text": "A\nB", "source_language": "", "custom_instructions": ""},
        )
        self.assertEqual(rendered.system, "first\nsecond")
        self.assertEqual(rendered.user, "before\nA\nB\nafter")

    def test_literal_braces_use_standard_double_brace_escaping(self) -> None:
        template = PromptTemplate(
            PromptTask.PREPROCESSING,
            "Return {{\"answer\": true}}",
            "Text: {source_text}",
            ResponseMode.PLAIN_TEXT,
            variables=(VariableSpec("source_text", "Text"),),
        )
        rendered = render_prompt(template, {"source_text": "hello"})
        self.assertEqual(rendered.system, 'Return {"answer": true}')

    def test_unmatched_literal_brace_has_actionable_error(self) -> None:
        template = PromptTemplate(
            PromptTask.PREPROCESSING,
            "bad {",
            "{source_text}",
            ResponseMode.PLAIN_TEXT,
            variables=(VariableSpec("source_text", "Text"),),
        )
        with self.assertRaises(PromptTemplateError) as raised:
            render_prompt(template, {"source_text": "x"})
        self.assertEqual(raised.exception.code, "invalid_braces")

    def test_missing_and_unknown_variables_are_rejected(self) -> None:
        template = PromptTemplate(
            PromptTask.PREPROCESSING,
            "",
            "{source_text} {not_documented}",
            ResponseMode.PLAIN_TEXT,
            variables=(VariableSpec("source_text", "Text"),),
        )
        with self.assertRaises(PromptTemplateError) as unknown:
            render_prompt(template, {"source_text": "x", "not_documented": "y"})
        self.assertEqual(unknown.exception.code, "unknown_variable")

        template = template.with_custom_text(system_template="", user_template="{source_text}")
        with self.assertRaises(PromptTemplateError) as missing:
            render_prompt(template, {})
        self.assertEqual(missing.exception.code, "missing_variable")

    def test_attribute_access_and_format_specs_are_rejected(self) -> None:
        for text, code in (("{source_text.upper}", "unsafe_variable"), ("{source_text!r}", "unsupported_format")):
            template = PromptTemplate(
                PromptTask.PREPROCESSING,
                "",
                text,
                ResponseMode.PLAIN_TEXT,
                variables=(VariableSpec("source_text", "Text"),),
            )
            with self.subTest(text=text), self.assertRaises(PromptTemplateError) as raised:
                render_prompt(template, {"source_text": "x"})
            self.assertEqual(raised.exception.code, code)

    def test_structured_contract_must_be_visible_and_is_editable(self) -> None:
        with self.assertRaises(PromptTemplateError) as hidden:
            PromptTemplate(
                PromptTask.TEXT_SEGMENTATION,
                "system",
                "user",
                ResponseMode.STRUCTURED,
                "Return JSON.",
            )
        self.assertEqual(hidden.exception.code, "hidden_response_contract")

        default = default_prompt_registry().resolve(PromptTask.TEXT_SEGMENTATION)
        custom = default.with_custom_text(
            system_template="CUSTOM",
            user_template="{source_text}\nVISIBLE: {output_format_contract}",
            response_contract="My exact schema",
        )
        rendered = render_prompt(
            custom,
            {"source_text": "x", "source_language": "", "segmentation_instructions": ""},
        )
        self.assertEqual(rendered.system, "CUSTOM")
        self.assertIn("VISIBLE: My exact schema", rendered.user)
        self.assertEqual(rendered.preview()["responseContract"], "My exact schema")

    def test_plain_text_mode_needs_no_contract_or_structured_parser(self) -> None:
        template = default_prompt_registry().resolve(PromptTask.PREPROCESSING)
        rendered = render_prompt(
            template,
            {"source_text": "x", "source_language": "English", "custom_instructions": "normalize"},
        )
        self.assertIs(rendered.response_mode, ResponseMode.PLAIN_TEXT)
        self.assertEqual(rendered.response_contract, "")
        self.assertNotIn("output_format_contract", rendered.used_variables)

    def test_switching_to_plain_text_does_not_retain_a_hidden_contract(self) -> None:
        structured = default_prompt_registry().resolve(PromptTask.TEXT_SEGMENTATION)
        plain = structured.with_custom_text(
            system_template="Custom plain system",
            user_template="{source_text}",
            response_mode=ResponseMode.PLAIN_TEXT,
        )
        self.assertEqual(plain.response_contract, "")

    def test_profile_override_precedes_provider_override(self) -> None:
        registry = default_prompt_registry()
        base = registry.resolve(PromptTask.PREPROCESSING)
        provider = base.with_custom_text(system_template="provider", user_template="{source_text}")
        profile = base.with_custom_text(system_template="profile", user_template="{source_text}")
        registry.register_override(provider, provider_id="openai")
        registry.register_override(profile, profile_id="work")
        values = {"source_text": "x", "source_language": "", "custom_instructions": ""}
        self.assertEqual(registry.render(PromptTask.PREPROCESSING, values, provider_id="openai").system, "provider")
        self.assertEqual(
            registry.render(PromptTask.PREPROCESSING, values, provider_id="openai", profile_id="work").system,
            "profile",
        )

    def test_template_export_import_round_trip(self) -> None:
        original = default_prompt_registry().resolve(PromptTask.TRANSLATION_REVIEW)
        restored = PromptTemplate.from_dict(original.to_dict(), variables=original.variables)
        self.assertEqual(restored, original)

    def test_documented_variables_cover_release_contract(self) -> None:
        registry = default_prompt_registry()
        documented = {
            variable.name
            for template in registry.defaults.values()
            for variable in template.documented_variables
        }
        expected = {
            "source_text", "source_language", "target_language", "proficiency_level",
            "selected_vocabulary", "required_targets", "preferred_targets", "optional_targets",
            "excluded_targets", "user_translation", "reference_translation", "article_genre",
            "desired_length", "custom_instructions", "segmentation_instructions",
            "output_format_contract",
        }
        self.assertTrue(expected.issubset(documented))


if __name__ == "__main__":
    unittest.main()
