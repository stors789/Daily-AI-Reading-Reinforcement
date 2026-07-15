"""Explicit, serializable capability states shared by every DAIRR host.

Capabilities describe whether an operation can be used *now* and why not.
They deliberately do not encode platform names as behavior switches.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping


class CapabilityId(str, Enum):
    ANKI_CONNECTION = "anki_connection"
    INTERNAL_ANKI_APIS = "internal_anki_apis"
    REVIEW_HISTORY = "review_history"
    FSRS_VALUES = "fsrs_values"
    ARTICLE_HISTORY = "article_history"
    PASTED_TEXT_PRACTICE = "pasted_text_practice"
    TARGET_CARD_SCORING = "target_card_scoring"
    CUSTOM_PROMPTS = "custom_prompts"
    PROVIDER_REASONING = "provider_reasoning"
    CANCELLATION = "cancellation"


class CapabilityStatus(str, Enum):
    AVAILABLE = "available"
    TEMPORARILY_UNAVAILABLE = "temporarily_unavailable"
    UNAVAILABLE_IN_MODE = "unavailable_in_mode"
    ANKI_DISCONNECTED = "anki_disconnected"
    DATA_ABSENT = "data_absent"
    PROVIDER_UNSUPPORTED = "provider_unsupported"
    OPTIONAL_EXTENSION_REQUIRED = "optional_extension_required"


class CapabilityReason(str, Enum):
    NONE = "none"
    CONNECTION_FAILED = "connection_failed"
    TIMEOUT = "timeout"
    UNSUPPORTED_ACTION = "unsupported_action"
    PARTIAL_RESPONSE = "partial_response"
    MISSING_FIELD = "missing_field"
    FSRS_NOT_AVAILABLE = "fsrs_not_available"
    HOST_MODE_LIMITATION = "host_mode_limitation"
    PROVIDER_LIMITATION = "provider_limitation"
    OPTIONAL_EXTENSION_NOT_INSTALLED = "optional_extension_not_installed"
    PROFILE_CLOSED = "profile_closed"
    OPERATION_CANCELLED = "operation_cancelled"
    UNKNOWN = "unknown"


class Provenance(str, Enum):
    SHARED_CORE = "shared_core"
    ANKI_INTERNAL = "anki_internal"
    ANKICONNECT_STANDARD = "ankiconnect_standard"
    ANKICONNECT_OPTIONAL_EXTENSION = "ankiconnect_optional_extension"
    LOCAL_HISTORY = "local_history"
    PROVIDER_DECLARED = "provider_declared"
    USER_CONFIGURED = "user_configured"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class Capability:
    id: CapabilityId
    status: CapabilityStatus
    reason: CapabilityReason = CapabilityReason.NONE
    provenance: Provenance = Provenance.UNKNOWN
    detail: str = ""

    def __post_init__(self) -> None:
        if self.status is CapabilityStatus.AVAILABLE and self.reason is not CapabilityReason.NONE:
            raise ValueError("an available capability cannot have an unavailable reason")
        if self.status is not CapabilityStatus.AVAILABLE and self.reason is CapabilityReason.NONE:
            raise ValueError("an unavailable capability requires a reason")

    @property
    def available(self) -> bool:
        return self.status is CapabilityStatus.AVAILABLE

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.id.value,
            "status": self.status.value,
            "reason": self.reason.value,
            "provenance": self.provenance.value,
            "detail": self.detail,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "Capability":
        return cls(
            id=CapabilityId(str(payload["id"])),
            status=CapabilityStatus(str(payload["status"])),
            reason=CapabilityReason(str(payload.get("reason", "none"))),
            provenance=Provenance(str(payload.get("provenance", "unknown"))),
            detail=str(payload.get("detail") or ""),
        )


class CapabilitySet:
    """Immutable-by-convention lookup with safe bridge serialization."""

    def __init__(self, capabilities: Iterable[Capability] = ()) -> None:
        values: dict[CapabilityId, Capability] = {}
        for capability in capabilities:
            if capability.id in values:
                raise ValueError(f"duplicate capability: {capability.id.value}")
            values[capability.id] = capability
        self._values = values

    def get(self, capability_id: CapabilityId) -> Capability:
        try:
            return self._values[capability_id]
        except KeyError as exc:
            raise KeyError(f"capability was not declared: {capability_id.value}") from exc

    def is_available(self, capability_id: CapabilityId) -> bool:
        capability = self._values.get(capability_id)
        return bool(capability and capability.available)

    def to_dict(self) -> dict[str, dict[str, str]]:
        return {
            capability_id.value: capability.to_dict()
            for capability_id, capability in sorted(
                self._values.items(), key=lambda item: item[0].value
            )
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CapabilitySet":
        capabilities = []
        for key, value in payload.items():
            if not isinstance(value, Mapping):
                raise ValueError(f"invalid capability payload: {key}")
            row = dict(value)
            row.setdefault("id", key)
            capabilities.append(Capability.from_dict(row))
        return cls(capabilities)
