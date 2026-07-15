"""Qt-neutral lifecycle management for add-on background work.

The manager deliberately retains neither dialogs nor collection objects.  A
host supplies a weak callback (normally ``weakref.WeakMethod(dialog._emit)``)
and tasks obtain Anki state only inside the task itself.  This keeps late
``taskman`` callbacks harmless after a dialog closes or the profile unloads.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from concurrent.futures import CancelledError
from dataclasses import dataclass
from threading import RLock
from typing import Any, Callable, Mapping
from uuid import uuid4

try:
    from dairr_core.bridge_contract import (
        EVENT_OPERATION_ACCEPTED,
        EVENT_OPERATION_CANCELLED,
        EVENT_OPERATION_COMPLETED,
        EVENT_OPERATION_FAILED,
    )
    from dairr_core.operations import (
        CancellationToken,
        OperationCancelled,
        OperationContext,
        OperationError,
        public_operation_error,
    )
except ImportError:  # packaged add-on compatibility import
    from .dairr_core.bridge_contract import (  # type: ignore[import-not-found]
        EVENT_OPERATION_ACCEPTED,
        EVENT_OPERATION_CANCELLED,
        EVENT_OPERATION_COMPLETED,
        EVENT_OPERATION_FAILED,
    )
    from .dairr_core.operations import (  # type: ignore[import-not-found]
        CancellationToken,
        OperationCancelled,
        OperationContext,
        OperationError,
        public_operation_error,
    )


TERMINAL_STATES = frozenset({"completed", "failed", "cancelled", "discarded"})


@dataclass(frozen=True, slots=True)
class OperationSnapshot:
    operation_id: str
    request_id: str
    action: str
    status: str
    created_at: float
    finished_at: float | None = None
    result: Any = None
    error: Mapping[str, Any] | None = None

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "action": self.action,
            "status": self.status,
        }
        if self.status == "completed":
            payload["result"] = self.result
        elif self.status == "failed" and self.error is not None:
            payload["error"] = dict(self.error)
        return payload


@dataclass(slots=True)
class _OperationRecord:
    snapshot: OperationSnapshot
    context: OperationContext
    generation: int
    supersede_key: str | None
    success_event: str | None = None
    failure_event: str | None = None
    terminal_emitted: bool = False


class AddonBackgroundOperations:
    """Schedule, cancel, supersede, and safely deliver add-on work.

    ``schedule`` must behave like ``mw.taskman.run_in_background``.  ``emit``
    is a zero-argument weak resolver returning the current bridge emitter, or
    ``None`` once its dialog has been destroyed.
    """

    def __init__(
        self,
        schedule: Callable[[Callable[[], Any], Callable[[Any], None]], Any],
        emit: Callable[[], Callable[..., Any] | None],
        *,
        max_records: int = 128,
        ttl_seconds: float = 300.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_records < 1 or ttl_seconds <= 0:
            raise ValueError("operation retention limits must be positive")
        self._schedule = schedule
        self._resolve_emit = emit
        self._max_records = max_records
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._lock = RLock()
        self._generation = 0
        self._active = True
        self._records: OrderedDict[str, _OperationRecord] = OrderedDict()
        self._latest: dict[str, str] = {}

    @property
    def active(self) -> bool:
        with self._lock:
            return self._active

    def submit(
        self,
        request_id: str,
        action: str,
        task: Callable[[OperationContext], Any],
        *,
        operation_id: str | None = None,
        supersede_key: str | None = None,
        success_event: str | None = None,
        failure_event: str | None = None,
    ) -> str:
        request_id = str(request_id or uuid4().hex)
        operation_id = str(operation_id or uuid4().hex)
        action = str(action or "operation")
        if not operation_id.strip():
            raise ValueError("operation_id is required")
        with self._lock:
            if not self._active:
                raise OperationError(
                    "host_unavailable",
                    "The DAIRR window is no longer available.",
                )
            if operation_id in self._records:
                raise OperationError("duplicate_operation", "The operation ID is already in use.")
            if supersede_key:
                previous_id = self._latest.get(supersede_key)
                if previous_id:
                    self._cancel_locked(previous_id, discard=True)
                self._latest[supersede_key] = operation_id
            context = OperationContext(operation_id, CancellationToken())
            now = self._clock()
            record = _OperationRecord(
                OperationSnapshot(operation_id, request_id, action, "queued", now),
                context,
                self._generation,
                supersede_key,
                success_event,
                failure_event,
            )
            self._records[operation_id] = record
            self._prune_locked(now)
        self._emit(record, EVENT_OPERATION_ACCEPTED, {"action": action, "status": "queued"})

        def run() -> Any:
            context.cancellation.raise_if_cancelled()
            with self._lock:
                current = self._records.get(operation_id)
                if current is record and current.snapshot.status == "queued":
                    current.snapshot = OperationSnapshot(
                        operation_id, request_id, action, "running", now
                    )
            return task(context)

        def done(future: Any) -> None:
            try:
                result = future.result()
            except (OperationCancelled, CancelledError):
                self._finish_cancelled(record)
            except BaseException as exc:
                self._finish_failed(record, exc)
            else:
                self._finish_completed(record, result)

        try:
            self._schedule(run, done)
        except BaseException as exc:
            self._finish_failed(record, exc)
        return operation_id

    def cancel(self, operation_id: str) -> OperationSnapshot | None:
        with self._lock:
            record = self._records.get(str(operation_id))
            if record is None:
                return None
            if record.snapshot.status not in TERMINAL_STATES:
                record.context.cancellation.cancel()
                record.snapshot = OperationSnapshot(
                    record.snapshot.operation_id,
                    record.snapshot.request_id,
                    record.snapshot.action,
                    "cancelled",
                    record.snapshot.created_at,
                    self._clock(),
                )
            snapshot = record.snapshot
            should_emit = not record.terminal_emitted
            if snapshot.status in TERMINAL_STATES:
                record.terminal_emitted = True
        event = {
            "completed": EVENT_OPERATION_COMPLETED,
            "failed": EVENT_OPERATION_FAILED,
            "cancelled": EVENT_OPERATION_CANCELLED,
            "discarded": EVENT_OPERATION_CANCELLED,
        }.get(snapshot.status, "operationProgress")
        if should_emit:
            self._emit(record, event, snapshot.to_payload())
        return snapshot

    def status(self, operation_id: str) -> OperationSnapshot | None:
        with self._lock:
            self._prune_locked(self._clock())
            record = self._records.get(str(operation_id))
            return record.snapshot if record else None

    def invalidate(self) -> None:
        """Detach every callback and cooperatively cancel all work."""
        with self._lock:
            if not self._active:
                return
            self._active = False
            self._generation += 1
            now = self._clock()
            for record in self._records.values():
                if record.snapshot.status not in TERMINAL_STATES:
                    record.context.cancellation.cancel()
                    record.snapshot = OperationSnapshot(
                        record.snapshot.operation_id,
                        record.snapshot.request_id,
                        record.snapshot.action,
                        "discarded",
                        record.snapshot.created_at,
                        now,
                    )
            self._latest.clear()

    def _finish_completed(self, record: _OperationRecord, result: Any) -> None:
        if not self._claim_terminal(record):
            return
        record.snapshot = OperationSnapshot(
            record.snapshot.operation_id,
            record.snapshot.request_id,
            record.snapshot.action,
            "completed",
            record.snapshot.created_at,
            self._clock(),
            result=result,
        )
        record.terminal_emitted = True
        self._emit(record, EVENT_OPERATION_COMPLETED, record.snapshot.to_payload())
        if record.success_event:
            legacy_payload = result if isinstance(result, Mapping) else {"result": result}
            self._emit(record, record.success_event, legacy_payload)

    def _finish_failed(self, record: _OperationRecord, exc: BaseException) -> None:
        if isinstance(exc, OperationCancelled):
            self._finish_cancelled(record)
            return
        if not self._claim_terminal(record):
            return
        error = public_operation_error(exc).to_dict()
        record.snapshot = OperationSnapshot(
            record.snapshot.operation_id,
            record.snapshot.request_id,
            record.snapshot.action,
            "failed",
            record.snapshot.created_at,
            self._clock(),
            error=error,
        )
        record.terminal_emitted = True
        self._emit(record, EVENT_OPERATION_FAILED, record.snapshot.to_payload())
        if record.failure_event:
            self._emit(record, record.failure_event, {"message": error["message"]})

    def _finish_cancelled(self, record: _OperationRecord) -> None:
        with self._lock:
            current = self._records.get(record.snapshot.operation_id)
            if not self._deliverable_locked(record):
                return
            if current.terminal_emitted:
                return
            if current.snapshot.status not in TERMINAL_STATES:
                current.snapshot = OperationSnapshot(
                    current.snapshot.operation_id,
                    current.snapshot.request_id,
                    current.snapshot.action,
                    "cancelled",
                    current.snapshot.created_at,
                    self._clock(),
                )
            elif current.snapshot.status != "cancelled":
                return
            current.terminal_emitted = True
        self._emit(record, EVENT_OPERATION_CANCELLED, current.snapshot.to_payload())

    def _claim_terminal(self, record: _OperationRecord) -> bool:
        with self._lock:
            if not self._deliverable_locked(record):
                return False
            return record.snapshot.status not in TERMINAL_STATES

    def _deliverable_locked(self, record: _OperationRecord) -> bool:
        current = self._records.get(record.snapshot.operation_id)
        if not self._active or current is not record or record.generation != self._generation:
            return False
        if record.supersede_key and self._latest.get(record.supersede_key) != record.snapshot.operation_id:
            return False
        return True

    def _cancel_locked(self, operation_id: str, *, discard: bool) -> None:
        record = self._records.get(operation_id)
        if record is None or record.snapshot.status in TERMINAL_STATES:
            return
        record.context.cancellation.cancel()
        record.snapshot = OperationSnapshot(
            record.snapshot.operation_id,
            record.snapshot.request_id,
            record.snapshot.action,
            "discarded" if discard else "cancelled",
            record.snapshot.created_at,
            self._clock(),
        )

    def _emit(self, record: _OperationRecord, event: str, payload: Mapping[str, Any]) -> None:
        with self._lock:
            if not self._deliverable_locked(record):
                return
        emitter = self._resolve_emit()
        if emitter is None:
            self.invalidate()
            return
        try:
            emitter(
                event,
                dict(payload),
                request_id=record.snapshot.request_id,
                operation_id=record.snapshot.operation_id,
            )
        except (RuntimeError, ReferenceError):
            # Deleted Qt wrappers commonly raise RuntimeError on access.
            self.invalidate()

    def _prune_locked(self, now: float) -> None:
        expired = [
            operation_id
            for operation_id, record in self._records.items()
            if record.snapshot.finished_at is not None
            and now - record.snapshot.finished_at > self._ttl_seconds
        ]
        for operation_id in expired:
            self._records.pop(operation_id, None)
        while len(self._records) > self._max_records:
            operation_id, record = next(iter(self._records.items()))
            if record.snapshot.status not in TERMINAL_STATES:
                break
            self._records.pop(operation_id, None)
