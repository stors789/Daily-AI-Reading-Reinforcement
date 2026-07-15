from __future__ import annotations

import sys
import unittest
import weakref
from concurrent.futures import Future
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
for path in (
    ROOT / "packages" / "dairr_core" / "src",
    ROOT / "addon" / "daily_ai_reading_reinforcement",
):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from background_operations import AddonBackgroundOperations  # noqa: E402
from dairr_core.operations import OperationError  # noqa: E402


class _Scheduler:
    def __init__(self) -> None:
        self.jobs = []

    def __call__(self, task, done):
        self.jobs.append((task, done))

    def finish(self, index=0):
        task, done = self.jobs[index]
        future = Future()
        try:
            future.set_result(task())
        except BaseException as exc:
            future.set_exception(exc)
        done(future)


class _Sink:
    def __init__(self) -> None:
        self.events = []

    def emit(self, event, payload, **envelope):
        self.events.append((event, payload, envelope))


class AddonBackgroundOperationTests(unittest.TestCase):
    def manager(self):
        scheduler = _Scheduler()
        sink = _Sink()
        callback = weakref.WeakMethod(sink.emit)
        manager = AddonBackgroundOperations(scheduler, callback)
        return manager, scheduler, sink

    def test_operation_ids_and_terminal_envelope(self) -> None:
        manager, scheduler, sink = self.manager()
        operation_id = manager.submit("request-1", "work", lambda _context: {"ok": True})
        self.assertEqual(sink.events[0][0], "operationAccepted")
        self.assertEqual(sink.events[0][2]["request_id"], "request-1")
        self.assertEqual(sink.events[0][2]["operation_id"], operation_id)

        scheduler.finish()

        self.assertEqual(sink.events[-1][0], "operationCompleted")
        self.assertEqual(sink.events[-1][1]["result"], {"ok": True})
        self.assertEqual(manager.status(operation_id).status, "completed")

    def test_cancel_is_idempotent_and_late_result_is_ignored(self) -> None:
        manager, scheduler, sink = self.manager()
        operation_id = manager.submit("request", "work", lambda context: context.cancellation.raise_if_cancelled())

        first = manager.cancel(operation_id)
        second = manager.cancel(operation_id)
        self.assertEqual(first.status, "cancelled")
        self.assertEqual(second.status, "cancelled")
        scheduler.finish()

        self.assertEqual([event[0] for event in sink.events].count("operationCancelled"), 1)
        self.assertNotIn("operationCompleted", [event[0] for event in sink.events])

    def test_invalidate_detaches_callbacks_for_profile_or_dialog_close(self) -> None:
        manager, scheduler, sink = self.manager()
        operation_id = manager.submit("request", "work", lambda _context: "private result")
        manager.invalidate()

        scheduler.finish()

        self.assertEqual([event[0] for event in sink.events], ["operationAccepted"])
        self.assertEqual(manager.status(operation_id).status, "discarded")
        with self.assertRaises(OperationError):
            manager.submit("another", "work", lambda _context: None)

    def test_supersession_discards_stale_result(self) -> None:
        manager, scheduler, sink = self.manager()
        first = manager.submit("one", "preview", lambda _context: "old", supersede_key="preview")
        second = manager.submit("two", "preview", lambda _context: "new", supersede_key="preview")

        scheduler.finish(0)
        scheduler.finish(1)

        completed = [event for event in sink.events if event[0] == "operationCompleted"]
        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0][1]["result"], "new")
        self.assertEqual(manager.status(first).status, "discarded")
        self.assertEqual(manager.status(second).status, "completed")

    def test_unknown_failures_are_redacted(self) -> None:
        manager, scheduler, sink = self.manager()

        def fail(_context):
            raise RuntimeError("diary text and sk-secret")

        manager.submit("request", "review", fail)
        scheduler.finish()

        error = sink.events[-1][1]["error"]
        self.assertEqual(error["code"], "operation_failed")
        self.assertNotIn("diary", str(error))
        self.assertNotIn("secret", str(error))


if __name__ == "__main__":
    unittest.main()
