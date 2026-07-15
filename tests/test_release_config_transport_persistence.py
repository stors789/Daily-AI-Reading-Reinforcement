from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
import threading
import unittest
import urllib.error
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parent.parent
CORE_SRC = ROOT / "packages" / "dairr_core" / "src"
DESKTOP = ROOT / "desktop_mock"
for path in (CORE_SRC, DESKTOP):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from dairr_core.article import load_saved_article, save_article, update_article_manifest
from dairr_core.atomic_persistence import atomic_write_text
from dairr_core.config import (
    CONFIG_SCHEMA_VERSION,
    export_prompt_registry_overrides,
    normalize_config,
    prompt_registry_from_config,
)
from dairr_core.llm import (
    OpenAICompatibleTransport,
    ProviderRequestCancelled,
    ProviderTransportError,
    generate_article,
    preview_chat_completion_request,
)
from dairr_core.operations import CancellationToken, ModelRequestSettings
from dairr_core.prompt import render_article_prompt
from dairr_core.prompt_templates import PromptTask, ResponseMode
from dairr_core.provider_capabilities import known_provider_capabilities
from dairr_core.scoring import recommended_preset
from desktop_adapters import DesktopConfigAdapter, DesktopDeckAdapter


class Response:
    def __init__(self, payload: object) -> None:
        self.body = json.dumps(payload).encode()

    def read(self) -> bytes:
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None


class Card:
    cid = 42
    term = "alpha"
    fields = {"Front": "alpha", "Back": "one"}
    is_new = False
    is_failed = True


class ReleaseConfigMigrationTests(unittest.TestCase):
    def test_legacy_config_migrates_without_losing_unknown_fields_or_keys(self) -> None:
        legacy = {
            "api_key": "local-secret",
            "ui_theme": "dark",
            "future_extension": {"keep": [1, 2]},
            "temperature": 0,
            "llm_api_profiles": [{
                "id": "work", "name": "Work", "api_key": "profile-secret",
                "custom_provider_flag": True, "temperature": 0,
            }],
        }
        migrated = normalize_config(legacy)
        self.assertEqual(migrated["config_schema_version"], CONFIG_SCHEMA_VERSION)
        self.assertEqual(migrated["api_key"], "local-secret")
        self.assertEqual(migrated["ui_theme"], "dark")
        self.assertEqual(migrated["future_extension"], {"keep": [1, 2]})
        self.assertEqual(migrated["temperature"], 0)
        self.assertEqual(migrated["llm_api_profiles"][0]["custom_provider_flag"], True)
        self.assertEqual(migrated["llm_api_profiles"][0]["api_key"], "profile-secret")

    def test_corrupt_optional_release_fields_fall_back_independently(self) -> None:
        migrated = normalize_config({
            "api_key": "keep",
            "temperature": "bad",
            "max_tokens": -4,
            "reasoning": {"mode": "explicit", "control": "effort"},
            "scoring_presets": [{"id": "broken"}],
            "ai_prompt_config": {"future": 7, "task_overrides": []},
        })
        self.assertEqual(migrated["api_key"], "keep")
        self.assertEqual(migrated["reasoning"], {"mode": "provider_default"})
        self.assertEqual(migrated["ai_prompt_config"]["future"], 7)
        self.assertTrue(migrated["scoring_presets"])

    def test_validated_nested_release_fields_retain_future_extensions(self) -> None:
        scoring = recommended_preset().to_dict()
        scoring["futurePresetOption"] = {"enabled": True}
        scoring["rules"]["again_count"]["futureTransformOption"] = 9
        migrated = normalize_config({
            "reasoning": {"mode": "disabled", "futureReasoningOption": "keep"},
            "scoring_presets": [scoring],
        })
        self.assertEqual(migrated["reasoning"]["futureReasoningOption"], "keep")
        restored = migrated["scoring_presets"][0]
        self.assertEqual(restored["futurePresetOption"], {"enabled": True})
        self.assertEqual(restored["rules"]["again_count"]["futureTransformOption"], 9)

    def test_prompt_task_provider_profile_overrides_round_trip(self) -> None:
        registry = prompt_registry_from_config({})
        base = registry.resolve(PromptTask.PREPROCESSING)
        registry.register_override(
            base.with_custom_text(system_template="provider", user_template="{source_text}"),
            provider_id="openai",
        )
        registry.register_override(
            base.with_custom_text(system_template="profile", user_template="{source_text}"),
            profile_id="work",
        )
        exported = export_prompt_registry_overrides(registry, existing={"future": "kept"})
        restored = prompt_registry_from_config({"ai_prompt_config": exported})
        self.assertEqual(exported["future"], "kept")
        self.assertEqual(restored.resolve(PromptTask.PREPROCESSING, provider_id="openai").system_template, "provider")
        self.assertEqual(restored.resolve(PromptTask.PREPROCESSING, provider_id="openai", profile_id="work").system_template, "profile")

    def test_desktop_config_write_is_private_atomic_and_round_trips_unknowns(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.json"
            adapter = DesktopConfigAdapter(str(path))
            adapter.save({"api_key": "secret", "future": {"x": 1}, "temperature": 0})
            loaded = DesktopConfigAdapter(str(path)).load()
            self.assertEqual(loaded["future"], {"x": 1})
            self.assertEqual(loaded["temperature"], 0)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_concurrent_config_writes_never_produce_partial_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.json"
            adapters = [DesktopConfigAdapter(str(path)) for _ in range(8)]
            threads = [threading.Thread(target=a.save, args=({"writer": i, "api_key": f"key-{i}"},)) for i, a in enumerate(adapters)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            payload = json.loads(path.read_text())
            self.assertIn(payload["writer"], range(8))
            self.assertTrue(payload["api_key"].startswith("key-"))

    def test_failed_atomic_replace_keeps_previous_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "record.json"
            path.write_text("old", encoding="utf-8")
            with patch("dairr_core.atomic_persistence.os.replace", side_effect=OSError("simulated")):
                with self.assertRaises(OSError):
                    atomic_write_text(path, "new", private=True)
            self.assertEqual(path.read_text(encoding="utf-8"), "old")
            self.assertEqual(list(path.parent.glob(f".{path.name}.*.tmp")), [])


class ProviderTransportIntegrationTests(unittest.TestCase):
    def config(self, **changes):
        config = normalize_config({
            "api_key": "super-secret-key",
            "base_url": "https://api.example.test/v1",
            "model": "model-a",
            "selected_provider_profile": "openrouter",
            "temperature": 0,
            "max_tokens": 123,
            "reasoning": {"mode": "disabled"},
        })
        config.update(changes)
        return config

    def preset(self):
        return {"article_language": "Japanese", "difficulty": "N3", "max_words": "100"}

    def test_exact_preview_messages_are_the_wire_messages_and_zero_is_preserved(self) -> None:
        config = self.config()
        rendered = render_article_prompt(config, "Deck", [Card()], ["Front"], self.preset())
        preview = preview_chat_completion_request(config, rendered)
        captured = {}

        def opener(request, timeout=None):
            captured.update(json.loads(request.data))
            return Response({"choices": [{"message": {"content": '{"title":"T","article":"A"}'}}]})

        with patch("urllib.request.urlopen", opener):
            generate_article(config, "Deck", [Card()], ["Front"], self.preset())
        self.assertEqual(captured["messages"], preview["prompt"]["messages"])
        self.assertEqual(captured["temperature"], 0)
        self.assertNotIn("reasoning", captured)
        self.assertNotIn("reasoning_effort", captured)
        self.assertEqual(captured["response_format"], {"type": "json_object"})

    def test_explicit_reasoning_uses_provider_mapping(self) -> None:
        config = self.config(reasoning={"mode": "explicit", "control": "effort", "effort": "high"})
        captured = {}

        def opener(request, timeout=None):
            captured.update(json.loads(request.data))
            return Response({"choices": [{"message": {"content": '{"article":"A"}'}}]})

        with patch("urllib.request.urlopen", opener):
            generate_article(config, "Deck", [Card()], ["Front"], self.preset())
        self.assertEqual(captured["reasoning"], {"effort": "high"})

    def test_shared_service_transport_submits_prebuilt_request_unchanged(self) -> None:
        config = self.config()
        rendered = render_article_prompt(config, "Deck", [Card()], ["Front"], self.preset())
        # ModelRequestSettings requires an intent; construct through the same
        # config-normalized path used by the application.
        from dairr_core.config import reasoning_intent_from_config

        request = ModelRequestSettings(
            "model-a",
            max_output_tokens=123,
            temperature=0,
            reasoning=reasoning_intent_from_config(config["reasoning"]),
            use_native_structured_output=True,
        ).build(known_provider_capabilities("openrouter"), rendered)
        captured = {}

        def opener(http_request, timeout=None):
            captured.update(json.loads(http_request.data))
            return Response({"choices": [{"message": {"content": '{"article":"A"}'}, "finish_reason": "stop"}]})

        with patch("urllib.request.urlopen", opener):
            response = OpenAICompatibleTransport(config).complete(
                request, cancellation=CancellationToken()
            )
        self.assertEqual(captured, request.body)
        self.assertEqual(response.content, '{"article":"A"}')
        self.assertEqual(response.finish_reason, "stop")

    def test_http_error_never_exposes_provider_body_key_or_prompt(self) -> None:
        config = self.config()
        private_prompt = "PRIVATE DIARY CONTENT"
        config["prompt_template"] = private_prompt

        def opener(request, timeout=None):
            raise urllib.error.HTTPError(
                request.full_url,
                401,
                "Unauthorized",
                {},
                BytesIO(b'{"error":"super-secret-key PRIVATE DIARY CONTENT"}'),
            )

        with patch("urllib.request.urlopen", opener), self.assertRaises(ProviderTransportError) as raised:
            generate_article(config, "Deck", [Card()], ["Front"], self.preset())
        message = str(raised.exception)
        self.assertIn("HTTP 401", message)
        self.assertNotIn("super-secret-key", message)
        self.assertNotIn(private_prompt, message)
        self.assertIsNone(raised.exception.__cause__)

    def test_cancelled_before_transport_performs_no_network_io(self) -> None:
        with patch("urllib.request.urlopen") as opener, self.assertRaises(ProviderRequestCancelled):
            generate_article(self.config(), "Deck", [Card()], ["Front"], self.preset(), cancelled=lambda: True)
        opener.assert_not_called()

    def test_malformed_provider_json_is_actionable_and_redacted(self) -> None:
        class BadResponse(Response):
            def __init__(self):
                self.body = b"secret malformed body"

        with patch("urllib.request.urlopen", lambda *_args, **_kwargs: BadResponse()), self.assertRaises(ProviderTransportError) as raised:
            generate_article(self.config(), "Deck", [Card()], ["Front"], self.preset())
        self.assertEqual(raised.exception.code, "malformed_provider_json")
        self.assertNotIn("secret", str(raised.exception))

    def test_unencodable_advanced_body_is_rejected_without_value_repr(self) -> None:
        private_value = object()
        config = self.config(extra_body={"vendor_setting": private_value})
        with self.assertRaises(ProviderTransportError) as raised:
            generate_article(config, "Deck", [Card()], ["Front"], self.preset())
        self.assertEqual(raised.exception.code, "invalid_provider_request")
        self.assertNotIn(repr(private_value), str(raised.exception))


class ArticlePersistenceReleaseTests(unittest.TestCase):
    def test_manifest_extends_history_and_preserves_unknown_fields_on_update(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            saved = save_article(
                "Deck",
                [Card()],
                "[ARTICLE_TITLE]\nTitle\n[MAIN_ARTICLE]\nBody",
                articles_dir=root,
                generation_metadata={
                    "target_usage": [{"target": "alpha", "surface": "alphas"}],
                    "unused_targets": ["beta"],
                    "target_reuse": {"alpha": 2},
                    "future_extension": {"keep": True},
                    "api_key": "must-not-persist",
                },
            )
            updated = update_article_manifest(
                str(saved["markdown"]), {"target_reuse": {"alpha": 3}}, articles_dir=root
            )
            loaded = load_saved_article(str(saved["markdown"]), articles_dir=root)
            serialized = json.dumps(updated)
            self.assertEqual(loaded["targetUsage"][0]["surface"], "alphas")
            self.assertEqual(loaded["targetReuse"], {"alpha": 3})
            self.assertEqual(updated["future_extension"], {"keep": True})
            self.assertNotIn("must-not-persist", serialized)

    def test_legacy_article_without_manifest_remains_loadable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            article = root / "legacy.md"
            article.write_text("---\ndeck: Old\nfuture_field: keep\n---\nLegacy body", encoding="utf-8")
            loaded = load_saved_article(str(article), articles_dir=root)
            self.assertEqual(loaded["article"], "Legacy body")
            self.assertEqual(loaded["metadata"], {})

    def test_prefix_and_symlink_escape_are_denied(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            root = base / "articles"
            root.mkdir()
            sibling = base / "articles-private.md"
            sibling.write_text("private", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "Access denied"):
                load_saved_article(str(sibling), articles_dir=root)
            outside = base / "outside.md"
            outside.write_text("private", encoding="utf-8")
            link = root / "escape.md"
            try:
                link.symlink_to(outside)
            except OSError:
                self.skipTest("symlinks unavailable")
            with self.assertRaisesRegex(RuntimeError, "Access denied"):
                load_saved_article(str(link), articles_dir=root)

    def test_two_desktop_adapters_do_not_share_or_mutate_global_destination(self) -> None:
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            a = DesktopDeckAdapter(first)
            b = DesktopDeckAdapter(second)
            results = []
            threads = [
                threading.Thread(target=lambda: results.append(a.save_article("A", [], "first"))),
                threading.Thread(target=lambda: results.append(b.save_article("B", [], "second"))),
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            parents = {item["markdown"].parent for item in results}
            self.assertEqual(parents, {Path(first) / "articles", Path(second) / "articles"})


if __name__ == "__main__":
    unittest.main()
