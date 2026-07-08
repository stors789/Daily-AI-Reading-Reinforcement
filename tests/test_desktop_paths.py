from __future__ import annotations

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

from desktop_adapters import DesktopConfigAdapter, DesktopDeckAdapter
from desktop_paths import app_config_path, app_output_dir, legacy_config_path


class TestDesktopPaths(unittest.TestCase):
    def test_macos_paths_use_application_support(self) -> None:
        home = Path("/Users/example")

        self.assertEqual(
            app_config_path(home=home, platform="darwin"),
            home / "Library" / "Application Support" / "DAIRR" / "config.json",
        )
        self.assertEqual(
            app_output_dir(home=home, platform="darwin"),
            home / "Library" / "Application Support" / "DAIRR" / "articles",
        )

    def test_windows_paths_use_appdata(self) -> None:
        appdata = Path("C:/Users/example/AppData/Roaming")

        self.assertEqual(
            app_config_path(
                home="C:/Users/example",
                environ={"APPDATA": str(appdata)},
                platform="win32",
            ),
            appdata / "DAIRR" / "config.json",
        )
        self.assertEqual(
            app_output_dir(
                home="C:/Users/example",
                environ={"APPDATA": str(appdata)},
                platform="win32",
            ),
            appdata / "DAIRR" / "articles",
        )

    def test_linux_paths_use_local_share(self) -> None:
        home = Path("/home/example")

        self.assertEqual(
            app_config_path(home=home, platform="linux"),
            home / ".local" / "share" / "dairr" / "config.json",
        )
        self.assertEqual(
            app_output_dir(home=home, platform="linux"),
            home / ".local" / "share" / "dairr" / "articles",
        )

    def test_legacy_config_path_uses_old_location(self) -> None:
        self.assertEqual(
            legacy_config_path(home="/Users/example"),
            Path("/Users/example") / ".dairr_config.json",
        )


class TestDesktopAdapterPathSelection(unittest.TestCase):
    def test_desktop_config_path_env_has_priority(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            env_config = tmp / "env-config.json"
            legacy_config = tmp / ".dairr_config.json"
            env_config.write_text(json.dumps({"ui_language": "env"}), encoding="utf-8")
            legacy_config.write_text(json.dumps({"ui_language": "legacy"}), encoding="utf-8")

            with patch.dict(
                os.environ,
                {
                    "DESKTOP_CONFIG_PATH": str(env_config),
                    "HOME": str(tmp),
                },
                clear=True,
            ):
                config = DesktopConfigAdapter().load()

        self.assertIsNotNone(config)
        self.assertEqual(config["ui_language"], "env")

    def test_legacy_config_is_read_when_env_path_is_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            legacy_config = tmp / ".dairr_config.json"
            legacy_config.write_text(json.dumps({"ui_language": "legacy"}), encoding="utf-8")

            with patch.dict(os.environ, {"HOME": str(tmp)}, clear=True):
                config = DesktopConfigAdapter().load()

        self.assertIsNotNone(config)
        self.assertEqual(config["ui_language"], "legacy")

    def test_new_app_config_path_is_used_without_env_or_legacy(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            expected = app_config_path(home=tmp, platform=sys.platform)

            with patch.dict(os.environ, {"HOME": str(tmp)}, clear=True):
                adapter = DesktopConfigAdapter()
                adapter.save({"ui_language": "new"})

            self.assertEqual(adapter._file_path, expected)
            self.assertTrue(expected.is_file())
            self.assertEqual(json.loads(expected.read_text(encoding="utf-8"))["ui_language"], "new")

    def test_desktop_output_dir_env_has_priority(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "fixed-output"

            with patch.dict(os.environ, {"DESKTOP_OUTPUT_DIR": str(output_dir)}, clear=True):
                adapter = DesktopDeckAdapter()

        self.assertEqual(adapter._output_dir, output_dir)
        self.assertEqual(adapter._articles_dir, output_dir / "articles")

    def test_default_output_dir_is_not_repo_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"HOME": tmpdir}, clear=True):
                adapter = DesktopDeckAdapter()

        self.assertNotEqual(adapter._output_dir, _mock_dir / "output")
        self.assertNotEqual(adapter._articles_dir, _mock_dir / "output" / "articles")
        self.assertEqual(adapter._articles_dir.name, "articles")

    def test_constructor_output_dir_remains_fixed_base_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = DesktopDeckAdapter(output_dir=tmpdir)
            result = adapter.save_article("Deck", [], "\nArticle body.")

        self.assertEqual(result["markdown"].parent, Path(tmpdir) / "articles")
        self.assertEqual(result["html"].parent, Path(tmpdir) / "articles")


if __name__ == "__main__":
    unittest.main()
