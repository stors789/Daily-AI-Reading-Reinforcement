from __future__ import annotations

import time
import unittest
from pathlib import Path
import sys


CORE_SRC = Path(__file__).resolve().parent.parent / "packages" / "dairr_core" / "src"
if str(CORE_SRC) not in sys.path:
    sys.path.insert(0, str(CORE_SRC))

from dairr_core.application_host import OperationRegistry
from dairr_core.bridge_contract import (
    BRIDGE_VERSION,
    BridgeRequest,
    failure_envelope,
    response_envelope,
)
from dairr_core.operations import OperationError


class BridgeContractTests(unittest.TestCase):
    def test_legacy_request_receives_generated_identity(self) -> None:
        request = BridgeRequest.from_mapping({"action": "load", "payload": {}})
        self.assertEqual(request.version, BRIDGE_VERSION)
        self.assertTrue(request.request_id)

    def test_response_and_failure_envelopes_retain_request_and_operation(self) -> None:
        response = response_envelope("request-1", "done", {"ok": True}, operation_id="operation-1")
        self.assertEqual(response["version"], BRIDGE_VERSION)
        self.assertEqual(response["requestId"], "request-1")
        self.assertEqual(response["operationId"], "operation-1")

        failed = failure_envelope(
            "request-1",
            OperationError("safe_code", "Safe message.", retryable=True),
            operation_id="operation-1",
        )
        self.assertEqual(failed["event"], "operationFailed")
        self.assertEqual(failed["payload"]["error"]["code"], "safe_code")
        self.assertNotIn("exception", str(failed).lower())

    def test_invalid_payload_and_request_id_are_rejected(self) -> None:
        with self.assertRaises(OperationError):
            BridgeRequest.from_mapping({"action": "load", "payload": []})
        with self.assertRaises(OperationError):
            BridgeRequest.from_mapping({"requestId": "../../bad", "action": "load", "payload": {}})


class OperationRegistryTests(unittest.TestCase):
    def test_async_completion_uses_original_request_identity(self) -> None:
        registry = OperationRegistry(max_workers=1, max_records=4, terminal_ttl_seconds=10)
        try:
            accepted = registry.submit("work", "request-original", lambda _context: {"value": 7})
            operation_id = accepted["operationId"]
            for _ in range(100):
                status = registry.status(operation_id)
                if status["event"] != "operationProgress":
                    break
                time.sleep(0.005)
            self.assertEqual(status["event"], "operationCompleted")
            self.assertEqual(status["requestId"], "request-original")
            self.assertEqual(status["payload"]["result"], {"value": 7})
        finally:
            registry.shutdown()

    def test_cancellation_is_idempotent_and_private_failure_is_redacted(self) -> None:
        registry = OperationRegistry(max_workers=1, max_records=4, terminal_ttl_seconds=10)
        try:
            def work(context):
                while not context.cancellation.cancelled:
                    time.sleep(0.002)
                context.cancellation.raise_if_cancelled()
                return {"privateText": "should not happen"}

            accepted = registry.submit("work", "request-cancel", work)
            first = registry.cancel(accepted["operationId"])
            second = registry.cancel(accepted["operationId"])
            self.assertEqual(first["event"], "operationCancelled")
            self.assertEqual(second["event"], "operationCancelled")
            self.assertEqual(first["payload"]["error"]["code"], "cancelled")
        finally:
            registry.shutdown()

    def test_unknown_exception_text_does_not_cross_registry(self) -> None:
        registry = OperationRegistry(max_workers=1, max_records=4, terminal_ttl_seconds=10)
        try:
            accepted = registry.submit(
                "work",
                "request-private",
                lambda _context: (_ for _ in ()).throw(RuntimeError("api_key=secret diary text")),
            )
            for _ in range(100):
                status = registry.status(accepted["operationId"])
                if status["event"] != "operationProgress":
                    break
                time.sleep(0.005)
            serialized = str(status)
            self.assertEqual(status["event"], "operationFailed")
            self.assertNotIn("secret", serialized)
            self.assertNotIn("diary", serialized)
        finally:
            registry.shutdown()


if __name__ == "__main__":
    unittest.main()
