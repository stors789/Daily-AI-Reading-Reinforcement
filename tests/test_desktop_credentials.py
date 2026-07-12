import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_repo_root = Path(__file__).resolve().parent.parent
_mock_dir = _repo_root / "desktop_mock"
if str(_mock_dir) not in sys.path:
    sys.path.insert(0, str(_mock_dir))

from desktop_adapters import DesktopConfigAdapter


class MemoryCredentials:
    def __init__(self, fail_write: bool = False) -> None:
        self.values: dict[str, str] = {}
        self.fail_write = fail_write

    def read(self, reference: str) -> str | None:
        return self.values.get(reference)

    def write(self, reference: str, secret: str) -> None:
        if self.fail_write:
            raise RuntimeError("keyring unavailable")
        self.values[reference] = secret

    def delete(self, reference: str) -> None:
        self.values.pop(reference, None)


class TestDesktopCredentials(unittest.TestCase):
    def test_save_externalizes_all_credentials_and_load_resolves_them(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.json"
            credentials = MemoryCredentials()
            config = {
                "api_key": "primary",
                "momo_api_key": "momo",
                "llm_api_profiles": [
                    {"id": "work", "model": "m", "api_key": "profile"},
                ],
            }
            DesktopConfigAdapter(str(path), credentials).save(config)

            raw = path.read_text(encoding="utf-8")
            self.assertNotIn("primary", raw)
            persisted = json.loads(raw)
            self.assertNotIn("api_key", persisted)
            self.assertNotIn("momo_api_key", persisted)
            self.assertNotIn("api_key", persisted["llm_api_profiles"][0])
            loaded = DesktopConfigAdapter(str(path), credentials).load()
            self.assertEqual(loaded["api_key"], "primary")
            self.assertEqual(loaded["momo_api_key"], "momo")
            self.assertEqual(loaded["llm_api_profiles"][0]["api_key"], "profile")

    def test_plaintext_migration_is_atomic_and_transparent(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.json"
            path.write_text(json.dumps({"api_key": "legacy", "ui_language": "zh"}), encoding="utf-8")
            credentials = MemoryCredentials()
            loaded = DesktopConfigAdapter(str(path), credentials).load()
            self.assertEqual(loaded["api_key"], "legacy")
            self.assertNotIn("legacy", path.read_text(encoding="utf-8"))

    def test_failed_migration_preserves_plaintext_file_and_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.json"
            original = json.dumps({"api_key": "legacy"})
            path.write_text(original, encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "keyring unavailable"):
                DesktopConfigAdapter(str(path), MemoryCredentials(fail_write=True)).load()
            self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_environment_api_key_is_not_written_to_keyring_or_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.json"
            credentials = MemoryCredentials()
            adapter = DesktopConfigAdapter(str(path), credentials)
            with patch.dict(os.environ, {"DAIRR_API_KEY": "environment-only"}):
                loaded = adapter.load()
                adapter.save(loaded)
            self.assertNotIn("environment-only", path.read_text(encoding="utf-8"))
            self.assertNotIn("environment-only", credentials.values.values())


if __name__ == "__main__":
    unittest.main()
