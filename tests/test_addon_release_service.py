from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
for path in (
    ROOT / "packages" / "dairr_core" / "src",
    ROOT / "addon" / "daily_ai_reading_reinforcement",
):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from addon_release_service import AddonReleaseService  # noqa: E402
from dairr_core.capabilities import CapabilitySet  # noqa: E402
from dairr_core.prompt_templates import PromptTask  # noqa: E402
from dairr_core.scoring import recommended_preset  # noqa: E402


class AddonReleaseServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.config = {
            "api_key": "secret",
            "base_url": "https://example.invalid/v1",
            "model": "test-model",
            "selected_provider_profile": "openai",
        }
        self.service = AddonReleaseService(
            lambda: dict(self.config),
            self._save,
            Path(self.temp.name),
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _save(self, value):
        self.config = dict(value)

    def test_pasted_practice_round_trip_uses_addon_history_root(self) -> None:
        created = self.service.create_pasted_practice({
            "sourceText": "First paragraph.\n\nSecond paragraph.",
            "sourceLanguage": "en",
            "targetLanguage": "ja",
            "save": True,
        })
        session = created["session"]
        self.assertEqual(len(session["segments"]), 2)
        self.assertNotIn("source_text", session)
        self.assertEqual(self.service.history_root, Path(self.temp.name))

        listed = self.service.list_practice_sessions()["sessions"]
        self.assertEqual([item["id"] for item in listed], [session["id"]])
        loaded = self.service.load_practice_session({"sessionId": session["id"]})
        self.assertEqual(loaded["session"]["sourceText"], session["sourceText"])

        drafted = self.service.save_practice_draft({
            "sessionId": session["id"],
            "translation": "下書き",
        })
        self.assertEqual(drafted["session"]["completeTextDraft"], "下書き")

    def test_unsaved_practice_remains_usable_in_memory(self) -> None:
        created = self.service.create_pasted_practice({
            "sourceText": "offline text",
            "sourceLanguage": "en",
            "targetLanguage": "ja",
            "save": False,
        })
        session_id = created["session"]["id"]
        self.assertEqual(self.service.repository.list_ids(), [])
        drafted = self.service.save_practice_draft({
            "sessionId": session_id,
            "translation": "draft",
            "save": False,
        })
        self.assertEqual(drafted["session"]["completeTextDraft"], "draft")
        self.assertEqual(self.service.repository.list_ids(), [])

    def test_scoring_prompt_and_reasoning_settings_persist_via_shared_config(self) -> None:
        scoring = self.service.get_scoring_config()
        self.assertEqual(scoring["selectedPresetId"], "recommended-v1")
        preset = recommended_preset().to_dict()
        preset["id"] = "mine"
        preset["name"] = "Mine"
        saved = self.service.save_scoring_config({"preset": preset})
        self.assertEqual(saved["selectedPresetId"], "mine")
        exported = self.service.export_scoring_config({"presetId": "mine"})
        self.assertIn('"id":"mine"', exported["serialized"])

        templates = self.service.list_prompt_templates()["templates"]
        article = next(item for item in templates if item["task"] == PromptTask.ARTICLE_GENERATION.value)
        article["systemTemplate"] = "Custom system"
        updated = self.service.save_prompt_template({"template": article})
        self.assertEqual(updated["template"]["systemTemplate"], "Custom system")
        self.assertNotIn("secret", str(self.service.get_reasoning_settings()))

        disabled = self.service.save_reasoning_settings({"reasoning": {"mode": "disabled"}})
        self.assertEqual(disabled["reasoning"], {"mode": "disabled"})
        preview = self.service.preview_reasoning_settings({})
        self.assertEqual(preview["effectiveSettings"]["reasoningMode"], "disabled")
        self.assertIsNone(preview["effectiveSettings"]["reasoningControl"])

    def test_capabilities_add_offline_practice_and_local_history(self) -> None:
        payload = self.service.capabilities(CapabilitySet())["capabilities"]
        self.assertEqual(payload["pasted_text_practice"]["status"], "available")
        self.assertEqual(payload["article_history"]["provenance"], "local_history")

    def test_prompt_preview_uses_unsaved_template_without_persisting(self) -> None:
        template = next(
            item for item in self.service.list_prompt_templates()["templates"]
            if item["task"] == "preprocessing"
        )
        template["systemTemplate"] = "Unsaved system"
        template["userTemplate"] = "Unsaved {source_text}"
        preview = self.service.preview_prompt({
            "task": "preprocessing",
            "template": template,
            "variables": {
                "source_text": "draft",
                "source_language": "en",
                "custom_instructions": "polish",
            },
            # Empty IDs preview the task-level editor rather than a provider
            # or profile override.
            "providerId": "",
            "profileId": "",
        })
        self.assertEqual(preview["preview"]["messages"][0]["content"], "Unsaved system")
        self.assertEqual(preview["preview"]["messages"][1]["content"], "Unsaved draft")
        stored = self.service.get_prompt_template({"task": "preprocessing"})
        self.assertNotEqual(stored["template"]["systemTemplate"], "Unsaved system")

    def test_ui_persist_and_revision_contract_rejects_stale_mutation(self) -> None:
        created = self.service.create_pasted_practice({
            "sourceText": "draft",
            "sourceLanguage": "en",
            "targetLanguage": "ja",
        })["session"]
        updated = self.service.save_practice_draft({
            "sessionId": created["id"],
            "revision": created["revision"],
            "translation": "first",
            "persist": False,
        })
        self.assertFalse(updated["persisted"])
        self.assertEqual(updated["session"]["revision"], created["revision"] + 1)
        with self.assertRaisesRegex(Exception, "changed in another operation"):
            self.service.save_practice_draft({
                "sessionId": created["id"],
                "revision": created["revision"],
                "translation": "stale",
                "persist": False,
            })

    def test_article_practice_loads_selected_history_path(self) -> None:
        article_root = Path(self.temp.name) / "articles"
        article_root.mkdir()
        article_path = article_root / "article.md"
        article_path.write_text(
            "---\ndeck: Words\ngenerated_at: 2026-07-16 12:00:00\n---\n"
            "[ARTICLE_TITLE]\nStory\n[MAIN_ARTICLE]\n日本語。\n[T] English.\n[REVIEW_NOTES]\n",
            encoding="utf-8",
        )
        created = self.service.create_article_practice({
            "articlePath": str(article_path),
            "sourceLanguage": "en",
            "targetLanguage": "ja",
            "direction": "back_translation",
            "save": False,
        })["session"]
        self.assertEqual(created["sourceText"], "English.")
        self.assertEqual(created["segments"][0]["referenceText"], "日本語。")
        self.assertEqual(created["articleReference"]["relativePath"], "article.md")


if __name__ == "__main__":
    unittest.main()
