from __future__ import annotations

import sys
import unittest
from pathlib import Path


CORE_SRC = Path(__file__).resolve().parent.parent / "packages" / "dairr_core" / "src"
if str(CORE_SRC) not in sys.path:
    sys.path.insert(0, str(CORE_SRC))

from dairr_core.operations import (
    CancellationToken,
    ModelRequestSettings,
    OperationCancelled,
    OperationContext,
    OperationError,
    public_operation_error,
    run_completion,
)
from dairr_core.prompt_templates import default_prompt_registry, PromptTask
from dairr_core.provider_capabilities import known_provider_capabilities


class BrokenTransport:
    def __init__(self, error):
        self.error = error

    def complete(self, request, *, cancellation):
        raise self.error


class OperationTests(unittest.TestCase):
    def test_cancellation_is_idempotent_and_runs_abort_hook_once(self) -> None:
        token = CancellationToken()
        called = []
        token.add_cancel_callback(lambda: called.append("abort"))
        self.assertTrue(token.cancel())
        self.assertFalse(token.cancel())
        self.assertEqual(called, ["abort"])
        with self.assertRaises(OperationCancelled):
            token.raise_if_cancelled()

    def test_late_cancel_callback_runs_immediately(self) -> None:
        token = CancellationToken()
        token.cancel()
        called = []
        token.add_cancel_callback(lambda: called.append(True))
        self.assertEqual(called, [True])

    def test_unknown_transport_error_is_redacted(self) -> None:
        prompt = default_prompt_registry().render(
            PromptTask.PREPROCESSING,
            {"source_text": "private diary", "source_language": "", "custom_instructions": "clean"},
        )
        request = ModelRequestSettings("model").build(known_provider_capabilities("custom"), prompt)
        with self.assertRaises(OperationError) as raised:
            run_completion(
                BrokenTransport(RuntimeError("api_key=secret private diary")),
                request,
                OperationContext(),
            )
        self.assertEqual(raised.exception.code, "provider_failed")
        self.assertNotIn("secret", str(raised.exception))
        self.assertNotIn("diary", str(raised.exception))

    def test_timeout_has_actionable_retryable_error(self) -> None:
        prompt = default_prompt_registry().render(
            PromptTask.PREPROCESSING,
            {"source_text": "x", "source_language": "", "custom_instructions": "x"},
        )
        request = ModelRequestSettings("model").build(known_provider_capabilities("custom"), prompt)
        with self.assertRaises(OperationError) as raised:
            run_completion(BrokenTransport(TimeoutError()), request, OperationContext())
        self.assertEqual(raised.exception.code, "provider_unavailable")
        self.assertTrue(raised.exception.retryable)

    def test_safe_error_details_drop_sensitive_fields(self) -> None:
        error = OperationError(
            "bad-input",
            "Try again.",
            safe_details={"attemptCount": 2, "api_token": "secret", "sourceText": "private"},
        )
        self.assertEqual(error.code, "bad_input")
        self.assertEqual(error.to_dict()["details"], {"attemptCount": 2})

    def test_public_error_preserves_only_declared_safe_errors(self) -> None:
        safe = OperationError("known", "Known safe message")
        self.assertIs(public_operation_error(safe), safe)
        redacted = public_operation_error(RuntimeError("private response"))
        self.assertEqual(str(redacted), "The operation failed.")


if __name__ == "__main__":
    unittest.main()
