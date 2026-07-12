"""Secure desktop credential storage backed by the operating system keyring.

This module deliberately has no plaintext fallback.  Callers may inject a
keyring-compatible backend for tests; production callers use ``keyring``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


SERVICE_NAME = "com.dairr.desktop.credentials.v1"
API_KEY_REFERENCE = "llm/default/api-key"
MOMO_API_KEY_REFERENCE = "momo/default/api-key"


class CredentialStoreError(RuntimeError):
    """Raised when secure credential storage is unavailable or fails."""


class KeyringBackend(Protocol):
    def get_password(self, service_name: str, username: str) -> str | None: ...

    def set_password(self, service_name: str, username: str, password: str) -> None: ...

    def delete_password(self, service_name: str, username: str) -> None: ...


def profile_api_key_reference(profile_id: str) -> str:
    """Return the stable keyring reference for an LLM profile API key."""
    normalized = profile_id.strip()
    if not normalized or any(character in normalized for character in "\r\n\0"):
        raise ValueError("profile_id must be non-empty and contain no control separators")
    return f"llm/profile/{normalized}/api-key"


@dataclass(frozen=True)
class KeyringCredentialStore:
    """Small fail-closed adapter around a keyring-compatible backend."""

    backend: KeyringBackend
    service_name: str = SERVICE_NAME

    @classmethod
    def system(cls) -> "KeyringCredentialStore":
        try:
            import keyring
            from keyring.backend import fail
        except (ImportError, ModuleNotFoundError) as exc:
            raise CredentialStoreError("Secure credential storage is unavailable") from exc

        backend = keyring.get_keyring()
        if isinstance(backend, fail.Keyring) or getattr(backend, "priority", 0) <= 0:
            raise CredentialStoreError("No usable system credential backend is available")
        return cls(backend=backend)

    def read(self, reference: str) -> str | None:
        reference = self._validate_reference(reference)
        try:
            return self.backend.get_password(self.service_name, reference)
        except Exception as exc:
            raise CredentialStoreError("Could not read the secure credential") from exc

    def write(self, reference: str, secret: str) -> None:
        reference = self._validate_reference(reference)
        if not isinstance(secret, str) or not secret:
            raise ValueError("secret must be a non-empty string")
        try:
            self.backend.set_password(self.service_name, reference, secret)
        except Exception as exc:
            raise CredentialStoreError("Could not write the secure credential") from exc

    def delete(self, reference: str) -> None:
        reference = self._validate_reference(reference)
        try:
            self.backend.delete_password(self.service_name, reference)
        except Exception as exc:
            # Missing credentials and unavailable backends are intentionally not
            # conflated: callers can use read() before delete for idempotency.
            raise CredentialStoreError("Could not delete the secure credential") from exc

    @staticmethod
    def _validate_reference(reference: str) -> str:
        if not isinstance(reference, str) or not reference.strip():
            raise ValueError("credential reference must be a non-empty string")
        if any(character in reference for character in "\r\n\0"):
            raise ValueError("credential reference contains an invalid character")
        return reference.strip()
