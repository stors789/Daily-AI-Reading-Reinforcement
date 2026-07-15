"""Versioned, privacy-safe host bridge envelopes.

The bridge remains JSON-shaped so the portable web UI can use the same
contract in the standalone application and the Anki add-on.  Hosts may deliver
events by HTTP polling or directly, but request and operation identity is
always explicit so a closed/replaced view can discard stale completions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Mapping
from uuid import uuid4

from .operations import OperationError, public_operation_error


BRIDGE_VERSION = 2
MAX_REQUEST_ID_LENGTH = 128
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")

EVENT_OPERATION_ACCEPTED = "operationAccepted"
EVENT_OPERATION_PROGRESS = "operationProgress"
EVENT_OPERATION_COMPLETED = "operationCompleted"
EVENT_OPERATION_FAILED = "operationFailed"
EVENT_OPERATION_CANCELLED = "operationCancelled"

CONTROL_ACTIONS = frozenset({"operationStatus", "cancelOperation"})
ASYNC_ACTIONS = frozenset(
    {
        "submitPracticeReview",
        "generateTargetAware",
        "loadStudySignals",
        "previewScoring",
    }
)

RELEASE_ACTIONS = frozenset(
    {
        "getCapabilities",
        "createPastedPractice",
        "createArticlePractice",
        "listPracticeSessions",
        "loadPracticeSession",
        "savePracticeDraft",
        "updatePracticeSegments",
        "submitPracticeReview",
        "deletePracticeSession",
        "getScoringConfig",
        "saveScoringConfig",
        "resetScoringConfig",
        "importScoringConfig",
        "exportScoringConfig",
        "previewScoring",
        "listPromptTemplates",
        "getPromptTemplate",
        "savePromptTemplate",
        "resetPromptTemplate",
        "importPromptTemplates",
        "exportPromptTemplates",
        "previewPrompt",
        "getReasoningSettings",
        "saveReasoningSettings",
        "previewReasoningSettings",
        "generateTargetAware",
        "loadStudySignals",
        *CONTROL_ACTIONS,
    }
)

SYNC_EVENT_BY_ACTION = {
    "getCapabilities": "capabilitiesLoaded",
    "createPastedPractice": "practiceSessionCreated",
    "createArticlePractice": "practiceSessionCreated",
    "listPracticeSessions": "practiceSessionsLoaded",
    "loadPracticeSession": "practiceSessionLoaded",
    "savePracticeDraft": "practiceDraftSaved",
    "updatePracticeSegments": "practiceSegmentsUpdated",
    "deletePracticeSession": "practiceSessionDeleted",
    "getScoringConfig": "scoringConfigLoaded",
    "saveScoringConfig": "scoringConfigLoaded",
    "resetScoringConfig": "scoringConfigLoaded",
    "importScoringConfig": "scoringConfigLoaded",
    "exportScoringConfig": "scoringConfigExported",
    "listPromptTemplates": "promptTemplatesLoaded",
    "getPromptTemplate": "promptTemplateLoaded",
    "savePromptTemplate": "promptTemplateSaved",
    "resetPromptTemplate": "promptTemplateReset",
    "importPromptTemplates": "promptTemplatesLoaded",
    "exportPromptTemplates": "promptTemplatesExported",
    "previewPrompt": "promptPreview",
    "getReasoningSettings": "reasoningSettingsLoaded",
    "saveReasoningSettings": "reasoningSettingsLoaded",
    "previewReasoningSettings": "reasoningSettingsPreview",
}


@dataclass(frozen=True, slots=True)
class BridgeRequest:
    action: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    request_id: str = field(default_factory=lambda: uuid4().hex)
    version: int = BRIDGE_VERSION

    def __post_init__(self) -> None:
        if not self.action.strip() or len(self.action) > 96:
            raise OperationError("invalid_action", "A valid bridge action is required.")
        if not _SAFE_ID.fullmatch(self.request_id):
            raise OperationError("invalid_request_id", "The bridge request identifier is invalid.")
        if self.version not in (1, BRIDGE_VERSION):
            raise OperationError("unsupported_bridge_version", "This bridge request version is unsupported.")

    @classmethod
    def from_mapping(cls, message: Mapping[str, Any]) -> "BridgeRequest":
        payload = message.get("payload")
        if payload is None:
            payload = {}
        if not isinstance(payload, Mapping):
            raise OperationError("invalid_payload", "The bridge payload must be an object.")
        raw_id = str(message.get("requestId") or "").strip()
        request_id = raw_id or uuid4().hex
        raw_version = message.get("version", BRIDGE_VERSION)
        try:
            version = int(raw_version)
        except (TypeError, ValueError) as exc:
            raise OperationError("invalid_bridge_version", "The bridge request version is invalid.") from exc
        return cls(
            action=str(message.get("action") or ""),
            payload=dict(payload),
            request_id=request_id,
            version=version,
        )


def response_envelope(
    request_id: str,
    event: str,
    payload: Mapping[str, Any] | None = None,
    *,
    operation_id: str | None = None,
) -> dict[str, Any]:
    response: dict[str, Any] = {
        "version": BRIDGE_VERSION,
        "requestId": request_id,
        "event": str(event),
        "payload": dict(payload or {}),
    }
    if operation_id:
        response["operationId"] = operation_id
    return response


def failure_envelope(
    request_id: str,
    exc: BaseException,
    *,
    operation_id: str | None = None,
    code: str = "operation_failed",
    message: str = "The operation failed.",
) -> dict[str, Any]:
    safe = public_operation_error(exc, code=code, message=message)
    event = EVENT_OPERATION_CANCELLED if safe.code == "cancelled" else EVENT_OPERATION_FAILED
    return response_envelope(
        request_id,
        event,
        {
            "status": "cancelled" if event == EVENT_OPERATION_CANCELLED else "failed",
            "error": safe.to_dict(),
        },
        operation_id=operation_id,
    )
