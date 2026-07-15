from __future__ import annotations

import subprocess
import sys
import tempfile
import types
import importlib
import json
import unittest
from pathlib import Path
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parent.parent
ARCHIVE = ROOT / "dist" / "daily_ai_reading_reinforcement.ankiaddon"


class AddonReleasePackagingTests(unittest.TestCase):
    def test_release_services_and_shared_contract_are_vendored(self) -> None:
        completed = subprocess.run(
            [sys.executable, "package_addon.py"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        with ZipFile(ARCHIVE) as archive:
            names = set(archive.namelist())
            packaged_config = json.loads(archive.read("config.json"))
        self.assertIn("addon_release_service.py", names)
        self.assertIn("background_operations.py", names)
        self.assertIn("dialog_lifecycle.py", names)
        self.assertIn("anki_data_adapter.py", names)
        self.assertIn("dairr_core/bridge_contract.py", names)
        self.assertIn("dairr_core/application_host.py", names)
        self.assertIn("user_files/README.txt", names)
        self.assertFalse(any(
            name.startswith("user_files/") and name != "user_files/README.txt"
            for name in names
        ))
        self.assertFalse(any(name.startswith("user_files/practice_sessions/") for name in names))
        self.assertFalse(any("__pycache__" in name or name.endswith(".pyc") for name in names))
        self.assertFalse(packaged_config.get("api_key"))
        self.assertFalse(packaged_config.get("momo_api_key"))

    def test_config_sanitizer_removes_nested_credentials(self) -> None:
        from package_addon import _redact_secrets

        sanitized = _redact_secrets({
            "api_key": "top-secret",
            "momo_cookie": "private-cookie",
            "profiles": [{"api_key": "nested-secret", "model": "safe-model"}],
            "extension": {"access_token": "token-value", "safe": "kept"},
        })
        self.assertEqual(sanitized["api_key"], "")
        self.assertEqual(sanitized["momo_cookie"], "")
        self.assertEqual(sanitized["profiles"][0]["api_key"], "")
        self.assertEqual(sanitized["extension"]["access_token"], "")
        self.assertEqual(sanitized["extension"]["safe"], "kept")

    def test_vendored_release_service_imports_through_addon_package(self) -> None:
        subprocess.run([sys.executable, "package_addon.py"], cwd=ROOT, check=True, capture_output=True)
        with tempfile.TemporaryDirectory() as directory, ZipFile(ARCHIVE) as archive:
            archive.extractall(directory)
            package = types.ModuleType("_dairr_packaged_smoke")
            package.__path__ = [directory]
            sys.modules[package.__name__] = package
            try:
                module = importlib.import_module(f"{package.__name__}.addon_release_service")
                self.assertTrue(callable(module.AddonReleaseService))
            finally:
                for name in tuple(sys.modules):
                    if name == package.__name__ or name.startswith(f"{package.__name__}."):
                        sys.modules.pop(name, None)


if __name__ == "__main__":
    unittest.main()
