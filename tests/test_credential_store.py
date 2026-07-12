from __future__ import annotations

import unittest

from desktop_mock.credential_store import (
    API_KEY_REFERENCE,
    MOMO_API_KEY_REFERENCE,
    SERVICE_NAME,
    CredentialStoreError,
    KeyringCredentialStore,
    profile_api_key_reference,
)


class MemoryBackend:
    priority = 1

    def __init__(self):
        self.values = {}

    def get_password(self, service_name, username):
        return self.values.get((service_name, username))

    def set_password(self, service_name, username, password):
        self.values[(service_name, username)] = password

    def delete_password(self, service_name, username):
        del self.values[(service_name, username)]


class BrokenBackend(MemoryBackend):
    def get_password(self, service_name, username):
        raise RuntimeError("backend detail must not escape")

    def set_password(self, service_name, username, password):
        raise RuntimeError("backend detail must not escape")

    def delete_password(self, service_name, username):
        raise RuntimeError("backend detail must not escape")


class CredentialStoreTests(unittest.TestCase):
    def test_writes_reads_and_deletes_all_reference_kinds(self):
        backend = MemoryBackend()
        store = KeyringCredentialStore(backend)
        references = (
            API_KEY_REFERENCE,
            MOMO_API_KEY_REFERENCE,
            profile_api_key_reference("work-profile"),
        )
        for index, reference in enumerate(references):
            secret = f"secret-{index}"
            store.write(reference, secret)
            self.assertEqual(store.read(reference), secret)
            self.assertIn((SERVICE_NAME, reference), backend.values)
            store.delete(reference)
            self.assertIsNone(store.read(reference))

    def test_profile_reference_is_stable(self):
        self.assertEqual(
            profile_api_key_reference(" profile-123 "),
            "llm/profile/profile-123/api-key",
        )

    def test_invalid_values_are_rejected_before_backend_access(self):
        store = KeyringCredentialStore(MemoryBackend())
        for reference in ("", "  ", "bad\nreference"):
            with self.assertRaises(ValueError):
                store.read(reference)
        with self.assertRaises(ValueError):
            store.write(API_KEY_REFERENCE, "")
        with self.assertRaises(ValueError):
            profile_api_key_reference("")

    def test_backend_errors_are_fail_closed_and_sanitized(self):
        store = KeyringCredentialStore(BrokenBackend())
        for operation in (
            lambda: store.read(API_KEY_REFERENCE),
            lambda: store.write(API_KEY_REFERENCE, "secret"),
            lambda: store.delete(API_KEY_REFERENCE),
        ):
            with self.assertRaises(CredentialStoreError) as raised:
                operation()
            self.assertNotIn("backend detail", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
