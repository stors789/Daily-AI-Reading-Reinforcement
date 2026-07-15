"""Bounded asynchronous operation registry shared by DAIRR hosts."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from threading import Lock
import time
from typing import Any, Callable, Mapping
from uuid import uuid4

from .bridge_contract import (
    EVENT_OPERATION_ACCEPTED,
    EVENT_OPERATION_CANCELLED,
    EVENT_OPERATION_COMPLETED,
    EVENT_OPERATION_FAILED,
    EVENT_OPERATION_PROGRESS,
    failure_envelope,
    response_envelope,
)
from .operations import CancellationToken, OperationContext, OperationError


OperationCallable = Callable[[OperationContext], Mapping[str, Any]]


@dataclass(slots=True)
class OperationRecord:
    operation_id: str
    request_id: str
    action: str
    context: OperationContext
    created_at: float
    updated_at: float
    status: str = "queued"
    progress: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: OperationError | None = None
    future: Future[Mapping[str, Any]] | None = None


class OperationRegistry:
    """Run a finite number of jobs and retain a bounded terminal snapshot.

    Cancellation is cooperative.  Queued futures are cancelled immediately;
    already running provider/Anki transports observe the shared token before
    and after blocking I/O, with their finite network timeout as the hard bound.
    """

    def __init__(
        self,
        *,
        max_workers: int = 4,
        max_records: int = 128,
        terminal_ttl_seconds: float = 900,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not 1 <= max_workers <= 16:
            raise ValueError("max_workers must be between 1 and 16")
        if max_records < max_workers:
            raise ValueError("max_records must be at least max_workers")
        if terminal_ttl_seconds <= 0:
            raise ValueError("terminal_ttl_seconds must be positive")
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="dairr-operation")
        self._max_records = max_records
        self._terminal_ttl = float(terminal_ttl_seconds)
        self._clock = clock
        self._lock = Lock()
        self._records: dict[str, OperationRecord] = {}

    def submit(self, action: str, request_id: str, operation: OperationCallable) -> dict[str, Any]:
        now = self._clock()
        operation_id = uuid4().hex
        context = OperationContext(operation_id, CancellationToken())
        record = OperationRecord(operation_id, request_id, action, context, now, now)
        with self._lock:
            self._prune_locked(now)
            if len(self._records) >= self._max_records:
                raise OperationError(
                    "operation_capacity_reached",
                    "Too many operations are retained. Wait for current work to finish and try again.",
                    retryable=True,
                )
            self._records[operation_id] = record
            record.future = self._executor.submit(self._run, record, operation)
        return response_envelope(
            request_id,
            EVENT_OPERATION_ACCEPTED,
            {"action": action, "status": "queued"},
            operation_id=operation_id,
        )

    def _run(self, record: OperationRecord, operation: OperationCallable) -> Mapping[str, Any]:
        self._transition(record.operation_id, "running")
        try:
            record.context.cancellation.raise_if_cancelled()
            result = operation(record.context)
            if not isinstance(result, Mapping):
                raise OperationError("invalid_operation_result", "The operation returned an invalid result.")
            record.context.cancellation.raise_if_cancelled()
        except Exception as exc:
            safe = exc if isinstance(exc, OperationError) else OperationError(
                "operation_failed", "The operation failed.", retryable=False
            )
            self._fail(record.operation_id, safe)
            return {}
        self._complete(record.operation_id, dict(result))
        return result

    def progress(self, operation_id: str, payload: Mapping[str, Any]) -> bool:
        with self._lock:
            record = self._records.get(operation_id)
            if record is None or record.status not in {"queued", "running"}:
                return False
            record.progress = _safe_progress(payload)
            record.updated_at = self._clock()
            return True

    def status(self, operation_id: str) -> dict[str, Any]:
        with self._lock:
            self._prune_locked(self._clock())
            record = self._records.get(operation_id)
            if record is None:
                raise OperationError("unknown_operation", "The requested operation is no longer available.")
            if record.status in {"queued", "running"}:
                payload = {
                    "action": record.action,
                    "status": record.status,
                    "progress": _progress_value(record.progress),
                    **{key: value for key, value in record.progress.items() if key not in {"progress", "fraction"}},
                }
                return response_envelope(
                    record.request_id,
                    EVENT_OPERATION_PROGRESS,
                    payload,
                    operation_id=record.operation_id,
                )
            if record.status == "completed":
                return response_envelope(
                    record.request_id,
                    EVENT_OPERATION_COMPLETED,
                    {"action": record.action, "status": "completed", "result": dict(record.result or {})},
                    operation_id=record.operation_id,
                )
            if record.status == "cancelled":
                error = record.error or OperationError("cancelled", "The operation was cancelled.", retryable=True)
                return failure_envelope(record.request_id, error, operation_id=record.operation_id)
            error = record.error or OperationError("operation_failed", "The operation failed.")
            return failure_envelope(record.request_id, error, operation_id=record.operation_id)

    def cancel(self, operation_id: str) -> dict[str, Any]:
        with self._lock:
            record = self._records.get(operation_id)
            if record is None:
                raise OperationError("unknown_operation", "The requested operation is no longer available.")
            if record.status in {"completed", "failed", "cancelled"}:
                return self._status_locked(record)
            record.context.cancellation.cancel()
            if record.future is not None:
                record.future.cancel()
            record.status = "cancelled"
            record.error = OperationError("cancelled", "The operation was cancelled.", retryable=True)
            record.updated_at = self._clock()
            return self._status_locked(record)

    def _status_locked(self, record: OperationRecord) -> dict[str, Any]:
        if record.status == "completed":
            return response_envelope(
                record.request_id,
                EVENT_OPERATION_COMPLETED,
                {"action": record.action, "status": "completed", "result": dict(record.result or {})},
                operation_id=record.operation_id,
            )
        if record.status == "cancelled":
            return failure_envelope(
                record.request_id,
                record.error or OperationError("cancelled", "The operation was cancelled.", retryable=True),
                operation_id=record.operation_id,
            )
        if record.status == "failed":
            return failure_envelope(
                record.request_id,
                record.error or OperationError("operation_failed", "The operation failed."),
                operation_id=record.operation_id,
            )
        return response_envelope(
            record.request_id,
            EVENT_OPERATION_PROGRESS,
            {
                "action": record.action,
                "status": record.status,
                "progress": _progress_value(record.progress),
                **{key: value for key, value in record.progress.items() if key not in {"progress", "fraction"}},
            },
            operation_id=record.operation_id,
        )

    def _transition(self, operation_id: str, status: str) -> None:
        with self._lock:
            record = self._records.get(operation_id)
            if record is None or record.status == "cancelled":
                return
            record.status = status
            record.updated_at = self._clock()

    def _complete(self, operation_id: str, result: dict[str, Any]) -> None:
        with self._lock:
            record = self._records.get(operation_id)
            if record is None or record.status == "cancelled":
                return
            record.status = "completed"
            record.result = result
            record.updated_at = self._clock()

    def _fail(self, operation_id: str, error: OperationError) -> None:
        with self._lock:
            record = self._records.get(operation_id)
            if record is None or record.status == "cancelled":
                return
            record.status = "cancelled" if error.code == "cancelled" else "failed"
            record.error = error
            record.updated_at = self._clock()

    def _prune_locked(self, now: float) -> None:
        terminal = [
            record for record in self._records.values()
            if record.status in {"completed", "failed", "cancelled"}
        ]
        for record in terminal:
            if now - record.updated_at > self._terminal_ttl:
                self._records.pop(record.operation_id, None)
        if len(self._records) < self._max_records:
            return
        for record in sorted(terminal, key=lambda item: item.updated_at):
            if len(self._records) < self._max_records:
                break
            self._records.pop(record.operation_id, None)

    def shutdown(self, *, wait: bool = False) -> None:
        with self._lock:
            active = list(self._records.values())
        for record in active:
            if record.status in {"queued", "running"}:
                record.context.cancellation.cancel()
        self._executor.shutdown(wait=wait, cancel_futures=True)


def _safe_progress(payload: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in payload.items():
        name = str(key)[:80]
        lowered = name.lower()
        if any(part in lowered for part in ("text", "prompt", "translation", "content", "key", "token")):
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            result[name] = value if not isinstance(value, str) else value[:200]
    return result


def _progress_value(payload: Mapping[str, Any]) -> float:
    try:
        value = float(payload.get("progress", payload.get("fraction", 0.2)))
    except (TypeError, ValueError):
        return 0.2
    return max(0.0, min(100.0, value))
