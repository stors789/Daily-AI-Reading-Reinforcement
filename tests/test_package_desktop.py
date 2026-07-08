"""Tests for the desktop PyInstaller packaging scaffold."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock


_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

import package_desktop


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestPackageDesktopCommand(unittest.TestCase):
    def test_dry_run_browser_builds_expected_command(self) -> None:
        stdout = StringIO()

        exit_code = package_desktop.run_packager(
            ["--entry", "browser", "--dry-run", "--onefile", "--windowed", "--clean"],
            stdout=stdout,
        )

        self.assertEqual(exit_code, 0)
        output = stdout.getvalue()
        self.assertIn("pyinstaller", output)
        self.assertIn("--name DAIRR", output)
        self.assertIn("--onefile", output)
        self.assertIn("--windowed", output)
        self.assertIn("--clean", output)
        self.assertIn("--noconfirm", output)
        self.assertIn("--hidden-import datetime", output)
        self.assertIn("--hidden-import http.server", output)
        self.assertIn("--hidden-import urllib.error", output)
        self.assertIn("--hidden-import urllib.request", output)
        self.assertIn("--hidden-import uuid", output)
        self.assertIn("addon/daily_ai_reading_reinforcement/core", output)
        self.assertIn("addon/daily_ai_reading_reinforcement/web", output)
        self.assertIn("desktop_mock/main.py", output)
        self.assertIn("desktop_mock/diagnostics.py", output)
        self.assertNotIn("desktop_mock/output", output)
        self.assertIn("desktop_app.py", output)

    def test_dry_run_native_builds_expected_command(self) -> None:
        stdout = StringIO()

        exit_code = package_desktop.run_packager(
            ["--entry", "native", "--name", "DAIRR Native", "--dry-run"],
            stdout=stdout,
        )

        self.assertEqual(exit_code, 0)
        output = stdout.getvalue()
        self.assertIn("--name 'DAIRR Native'", output)
        self.assertIn("desktop_native.py", output)
        self.assertNotIn("desktop_app.py", output)

    def test_add_data_separator_by_platform(self) -> None:
        self.assertEqual(package_desktop.add_data_separator("win32"), ";")
        self.assertEqual(package_desktop.add_data_separator("darwin"), ":")
        self.assertEqual(package_desktop.add_data_separator("linux"), ":")

    def test_format_add_data_uses_platform_separator(self) -> None:
        source = Path("addon/daily_ai_reading_reinforcement/web")
        destination = Path("addon/daily_ai_reading_reinforcement/web")

        self.assertEqual(
            package_desktop.format_add_data(source, destination, "win32"),
            "addon/daily_ai_reading_reinforcement/web;addon/daily_ai_reading_reinforcement/web",
        )
        self.assertEqual(
            package_desktop.format_add_data(source, destination, "darwin"),
            "addon/daily_ai_reading_reinforcement/web:addon/daily_ai_reading_reinforcement/web",
        )
        self.assertEqual(
            package_desktop.format_add_data(source, destination, "linux"),
            "addon/daily_ai_reading_reinforcement/web:addon/daily_ai_reading_reinforcement/web",
        )

    def test_pyinstaller_missing_non_dry_run_returns_non_zero(self) -> None:
        stderr = StringIO()
        subprocess_run = MagicMock()

        exit_code = package_desktop.run_packager(
            ["--entry", "browser"],
            which=lambda name: None,
            subprocess_run=subprocess_run,
            stderr=stderr,
        )

        self.assertEqual(exit_code, 1)
        self.assertIn("PyInstaller is not installed", stderr.getvalue())
        subprocess_run.assert_not_called()

    def test_pyinstaller_present_calls_subprocess_run(self) -> None:
        completed = MagicMock(returncode=0)
        subprocess_run = MagicMock(return_value=completed)

        exit_code = package_desktop.run_packager(
            ["--entry", "native", "--windowed"],
            which=lambda name: "/venv/bin/pyinstaller",
            subprocess_run=subprocess_run,
        )

        self.assertEqual(exit_code, 0)
        subprocess_run.assert_called_once()
        command = subprocess_run.call_args.args[0]
        self.assertEqual(command[0], "/venv/bin/pyinstaller")
        self.assertIn("--windowed", command)
        self.assertIn(str(package_desktop.ENTRY_POINTS["native"]), command)
        self.assertEqual(subprocess_run.call_args.kwargs, {"check": False})

    def test_import_package_desktop_does_not_execute_build(self) -> None:
        mod = _load_module("dairr_package_desktop_import_probe", _repo_root / "package_desktop.py")

        self.assertTrue(hasattr(mod, "run_packager"))


if __name__ == "__main__":
    unittest.main()
