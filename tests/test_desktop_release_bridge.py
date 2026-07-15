from __future__ import annotations

import http.client
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

CORE_SRC = Path(__file__).resolve().parent.parent / "packages" / "dairr_core" / "src"
if str(CORE_SRC) not in sys.path:
    sys.path.insert(0, str(CORE_SRC))

from dairr_core.operations import ModelRequestSettings, ModelResponse, OperationContext
from dairr_core.provider_capabilities import known_provider_capabilities


MOCK_DIR = Path(__file__).resolve().parent.parent / "desktop_mock"
if str(MOCK_DIR) not in sys.path:
    sys.path.insert(0, str(MOCK_DIR))

spec = importlib.util.spec_from_file_location("dairr_release_main", MOCK_DIR / "main.py")
assert spec is not None and spec.loader is not None
main = importlib.util.module_from_spec(spec)
spec.loader.exec_module(main)


def request(action: str, payload=None, request_id="request-1"):
    return main.handle_bridge_message({
        "version": 2,
        "requestId": request_id,
        "action": action,
        "payload": payload or {},
    })


class DesktopReleaseBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict(os.environ, {
            "DESKTOP_OUTPUT_DIR": self.temp.name,
            "DESKTOP_CONFIG_PATH": str(Path(self.temp.name) / "config.json"),
            "DAIRR_DESKTOP_PROVIDER": "ankiconnect",
        }, clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)
        with main._PRACTICE_LOCK:
            main._PRACTICE_DRAFTS.clear()
            main._PRACTICE_REVISIONS.clear()

    def test_pasted_practice_is_available_without_anki_and_round_trips(self) -> None:
        with patch.object(main, "get_deck_provider", side_effect=AssertionError("Anki must not be contacted")):
            created = request("createPastedPractice", {
                "sourceText": "Private first paragraph.\n\nPrivate second paragraph.",
                "sourceLanguage": "en",
                "targetLanguage": "ja",
                "save": True,
            })
        self.assertEqual(created["event"], "practiceSessionCreated")
        session = created["payload"]["session"]
        self.assertEqual(len(session["segments"]), 2)
        listed = request("listPracticeSessions")
        self.assertEqual(len(listed["payload"]["sessions"]), 1)
        loaded = request("loadPracticeSession", {"sessionId": session["id"]})
        self.assertEqual(loaded["payload"]["session"]["sourceText"], session["sourceText"])

    def test_practice_revision_rejects_stale_mutation(self) -> None:
        created = request("createPastedPractice", {
            "sourceText": "One paragraph.", "sourceLanguage": "en", "targetLanguage": "ja",
        })["payload"]["session"]
        saved = request("savePracticeDraft", {
            "sessionId": created["id"], "revision": 0, "translation": "訳", "persist": False,
        })
        self.assertEqual(saved["payload"]["session"]["revision"], 1)
        stale = request("savePracticeDraft", {
            "sessionId": created["id"], "revision": 0, "translation": "古い訳", "persist": False,
        })
        self.assertEqual(stale["event"], "operationFailed")
        self.assertEqual(stale["payload"]["error"]["code"], "stale_practice_revision")
        self.assertNotIn("古い訳", str(stale))

    def test_article_back_translation_uses_translation_as_source_and_original_as_reference(self) -> None:
        saved = main.DesktopDeckAdapter().save_article(
            "Deck",
            [],
            "[ARTICLE_TITLE]\nStory\n[MAIN_ARTICLE]\nOriginal one.\n[T] Source one.\n\nOriginal two.\n[T] Source two.\n[REVIEW_NOTES]",
        )
        created = request("createArticlePractice", {
            "articlePath": str(saved["markdown"]),
            "sourceLanguage": "en",
            "targetLanguage": "ja",
            "direction": "back_translation",
            "save": True,
        })
        session = created["payload"]["session"]
        self.assertEqual(session["sourceText"], "Source one.\n\nSource two.")
        self.assertEqual(
            [item["referenceText"] for item in session["segments"]],
            ["Original one.", "Original two."],
        )
        self.assertEqual(session["articleReference"]["title"], "Story")

    def test_config_transport_never_returns_raw_keys(self) -> None:
        main.DesktopConfigAdapter().save({"api_key": "secret-api", "momo_api_key": "secret-momo"})
        result = request("getConfig")
        serialized = json.dumps(result)
        self.assertEqual(result["event"], "configLoaded")
        self.assertNotIn("secret-api", serialized)
        self.assertNotIn("secret-momo", serialized)
        self.assertNotIn('"api_key"', serialized)
        self.assertTrue(result["payload"]["apiSettings"]["hasApiKey"])

    def test_config_transport_does_not_echo_credentials_embedded_in_base_url(self) -> None:
        main.DesktopConfigAdapter().save({
            "api_key": "secret-api",
            "base_url": "https://user:embedded-secret@example.test/v1?token=also-secret",
            "model": "model",
        })
        result = request("getConfig")
        serialized = json.dumps(result)
        self.assertEqual(result["event"], "configLoaded")
        self.assertEqual(result["payload"]["apiSettings"]["baseUrl"], "")
        self.assertNotIn("embedded-secret", serialized)
        self.assertNotIn("also-secret", serialized)

        rejected = request("saveApiSettings", {
            "settings": {"providerId": "custom", "baseUrl": "https://user:secret@example.test", "model": "m"}
        })
        self.assertEqual(rejected["event"], "operationFailed")
        self.assertNotIn("user:secret", json.dumps(rejected))

    def test_capabilities_are_keyed_states_and_pasted_practice_stays_available(self) -> None:
        result = request("getCapabilities")
        capabilities = result["payload"]["capabilities"]
        self.assertEqual(capabilities["pasted_text_practice"]["status"], "available")
        self.assertIn("message", capabilities["anki_connection"])
        self.assertEqual(result["payload"]["practiceLimits"]["maxCharacters"], 100000)

    def test_study_signals_do_not_guess_authoritative_anki_day_bounds(self) -> None:
        import ankiconnect_data_adapter

        seen = {}

        class Adapter:
            issues = ()

            def __init__(self, provider):
                seen["provider"] = provider

            def collect_today_signals(self, *, day_start_ms=None, day_end_ms=None):
                seen["bounds"] = (day_start_ms, day_end_ms)
                return []

            def capabilities(self, *, authoritative_day_bounds=False):
                seen["authoritative"] = authoritative_day_bounds
                return main.CapabilitySet((
                    main.Capability(main.CapabilityId.ANKI_CONNECTION, main.CapabilityStatus.AVAILABLE,
                                    provenance=main.Provenance.ANKICONNECT_STANDARD),
                ))

        provider = object()
        with patch.object(main, "get_deck_provider", return_value=provider), patch.object(
            ankiconnect_data_adapter, "AnkiConnectDataAdapter", Adapter
        ):
            signals, _capabilities, _issues = main._load_study_signals({})
        self.assertEqual(signals, [])
        self.assertEqual(seen["bounds"], (None, None))
        self.assertFalse(seen["authoritative"])

    def test_prompt_edit_preview_reset_and_export(self) -> None:
        loaded = request("getPromptTemplate", {"task": "preprocessing", "scope": "task"})
        template = loaded["payload"]["template"]
        template["systemTemplate"] = "Custom system"
        template["userTemplate"] = "Text: {source_text}\nInstruction: {custom_instructions}"
        saved = request("savePromptTemplate", {"task": "preprocessing", "scope": "task", "template": template})
        self.assertEqual(saved["event"], "promptTemplateSaved")
        missing = request("previewPrompt", {
            "task": "preprocessing", "scope": "task", "values": {"source_text": "private"},
        })
        self.assertEqual(missing["payload"]["missingVariables"], ["custom_instructions"])
        preview = request("previewPrompt", {
            "task": "preprocessing", "scope": "task",
            "values": {"source_text": "private", "custom_instructions": "preserve"},
            "template": {**template, "systemTemplate": "Unsaved system"},
        })
        self.assertEqual(preview["payload"]["system"], "Unsaved system")
        self.assertIn("private", preview["payload"]["user"])
        reloaded = request("getPromptTemplate", {"task": "preprocessing", "scope": "task"})
        self.assertEqual(reloaded["payload"]["template"]["systemTemplate"], "Custom system")
        exported = request("exportPromptTemplates")
        self.assertIn("preprocessing", exported["payload"]["serialized"])
        reset = request("resetPromptTemplate", {"task": "preprocessing", "scope": "task"})
        self.assertNotEqual(reset["payload"]["template"]["systemTemplate"], "Custom system")

    def test_scoring_config_import_export_and_reasoning_preview(self) -> None:
        scoring = request("getScoringConfig")
        preset = scoring["payload"]["presets"][0]
        exported = request("exportScoringConfig", {"presetId": preset["id"]})
        imported = request("importScoringConfig", {"serialized": exported["payload"]["serialized"]})
        self.assertEqual(imported["payload"]["selectedPresetId"], preset["id"])

        reasoning = request("previewReasoningSettings", {"reasoning": {"mode": "disabled"}})
        self.assertEqual(reasoning["event"], "reasoningSettingsPreview")
        effective = reasoning["payload"]["effectiveSettings"]
        self.assertEqual(effective["reasoningMode"], "disabled")
        self.assertIsNone(effective["reasoningValue"])

        with patch.object(main, "_load_generation_config", return_value={
            "selected_provider_profile": "anthropic", "model": "claude", "max_tokens": 4000,
            "temperature": None, "reasoning": {"mode": "provider_default"},
        }), patch.object(main, "_save_desktop_config"):
            budget = request("saveReasoningSettings", {
                "reasoning": {"mode": "explicit", "control": "budget", "budgetTokens": 2048}
            })
        self.assertEqual(budget["event"], "reasoningSettingsLoaded")
        self.assertEqual(budget["payload"]["reasoning"]["budgetTokens"], 2048)
        self.assertNotIn("budget_tokens", budget["payload"]["reasoning"])

    def test_async_registry_retains_request_id_and_returns_terminal_result(self) -> None:
        with patch.object(main, "_run_release_operation", return_value={"candidateCount": 0}):
            accepted = request("loadStudySignals", request_id="request-signals")
            self.assertEqual(accepted["event"], "operationAccepted")
            for _ in range(100):
                status = request("operationStatus", {"operationId": accepted["operationId"]}, "poll-id")
                if status["event"] != "operationProgress":
                    break
                time.sleep(0.005)
        self.assertEqual(status["event"], "operationCompleted")
        self.assertEqual(status["requestId"], "request-signals")
        self.assertEqual(status["payload"]["result"]["candidateCount"], 0)

    def test_practice_review_service_boundary_persists_structured_feedback(self) -> None:
        created = request("createPastedPractice", {
            "sourceText": "I went home.", "sourceLanguage": "en", "targetLanguage": "ja",
        })["payload"]["session"]

        class Transport:
            def complete(self, _request, *, cancellation):
                cancellation.raise_if_cancelled()
                return ModelResponse(json.dumps({
                    "meaning": ["Meaning is preserved."],
                    "naturalness": ["Use a more idiomatic ending."],
                    "overall": "A strong alternative.",
                    "suggested_revision": "家に帰りました。",
                }))

        provider = known_provider_capabilities("custom")
        settings = ModelRequestSettings(model="test-model", use_native_structured_output=True)
        with patch.object(main, "_provider_context", return_value=("custom", provider, settings, Transport())):
            result = main._run_release_operation("submitPracticeReview", {
                "sessionId": created["id"], "revision": 0, "translation": "家へ帰った。", "persist": False,
            }, OperationContext("review-operation"))
        self.assertEqual(result["review"]["overall"], "A strong alternative.")
        self.assertEqual(result["review"]["suggestedRevision"], "家に帰りました。")
        self.assertEqual(len(result["session"]["attempts"]), 1)
        self.assertEqual(result["session"]["revision"], 1)

    def test_target_aware_generation_service_boundary_preserves_categories(self) -> None:
        class Transport:
            def complete(self, _request, *, cancellation):
                cancellation.raise_if_cancelled()
                return ModelResponse(json.dumps({
                    "title": "Natural story",
                    "article": "The required term appears naturally.",
                    "paragraph_translations": ["Translation"],
                    "target_usage": [{
                        "target_id": "required-1", "category": "required",
                        "actual_surface_forms": ["required term"], "status": "used",
                    }],
                    "unused_targets": [{"target_id": "optional-1", "reason": "Not natural here."}],
                }))

        provider = known_provider_capabilities("custom")
        settings = ModelRequestSettings(model="test-model", use_native_structured_output=True)
        with patch.object(main, "_provider_context", return_value=("custom", provider, settings, Transport())):
            result = main._run_release_operation("generateTargetAware", {
                "targetLanguage": "English",
                "targets": [
                    {"id": "required-1", "text": "required term", "category": "required"},
                    {"id": "optional-1", "text": "optional term", "category": "optional"},
                    {"id": "excluded-1", "text": "forbidden term", "category": "excluded"},
                ],
            }, OperationContext("generation-operation"))
        outcomes = {item["targetId"]: item for item in result["targetOutcomes"]}
        self.assertEqual(outcomes["required-1"]["category"], "required")
        self.assertEqual(outcomes["optional-1"]["category"], "optional")
        self.assertEqual(outcomes["excluded-1"]["status"], "excluded")
        self.assertEqual(result["title"], "Natural story")

    def test_real_generation_failure_does_not_become_mock_success(self) -> None:
        fake_source = type("Source", (), {"provider": object()})()
        with patch.object(main, "_resolve_deck_source", return_value=(fake_source, object())), patch.object(
            main, "resolve_generation_context", side_effect=RuntimeError("private source")
        ):
            result = main.handle_generate_real("deck", {})
        self.assertEqual(result["event"], "error")
        self.assertNotIn("[MAIN_ARTICLE]", str(result))
        self.assertNotIn("private source", str(result))


class DesktopHttpSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = main.ThreadingHTTPServer(("127.0.0.1", 0), main.MockHandler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def _post(self, *, token: str = "", host: str | None = None, origin: str | None = None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=2)
        headers = {"Content-Type": "application/json", "Host": host or f"127.0.0.1:{self.port}"}
        if token:
            headers[main.BRIDGE_TOKEN_HEADER] = token
        if origin:
            headers["Origin"] = origin
        connection.request("POST", "/api/bridge", json.dumps({
            "version": 2, "requestId": "http-request", "action": "getCapabilities", "payload": {},
        }), headers=headers)
        response = connection.getresponse()
        body = json.loads(response.read())
        connection.close()
        return response.status, response.getheaders(), body

    def test_bridge_requires_per_process_token(self) -> None:
        status, _headers, body = self._post()
        self.assertEqual(status, 403)
        self.assertEqual(body["payload"]["error"]["code"], "bridge_authorization_failed")
        status, _headers, body = self._post(token=main._BRIDGE_TOKEN)
        self.assertEqual(status, 200)
        self.assertEqual(body["event"], "capabilitiesLoaded")

    def test_host_and_origin_are_restricted_without_wildcard_cors(self) -> None:
        status, _headers, _body = self._post(token=main._BRIDGE_TOKEN, host="evil.example")
        self.assertEqual(status, 403)
        status, headers, _body = self._post(
            token=main._BRIDGE_TOKEN,
            origin="https://evil.example",
        )
        self.assertEqual(status, 403)
        self.assertNotEqual(dict(headers).get("Access-Control-Allow-Origin"), "*")

    def test_index_injects_token_without_exposing_it_in_health(self) -> None:
        page = main._build_index_page("test-token")
        self.assertIn("sendRequest(request)", page)
        self.assertIn("test-token", page)
        health = main.build_health_payload()
        self.assertNotIn("test-token", json.dumps(health))
        self.assertNotIn(main._BRIDGE_TOKEN, json.dumps(health))


if __name__ == "__main__":
    unittest.main()
