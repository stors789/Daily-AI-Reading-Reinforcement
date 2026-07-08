"""Tests for the optional pywebview native shell."""

from __future__ import annotations

import importlib.util
import os
import sys
import threading
import unittest
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

import desktop_native


def _raise_import_error():
    raise ImportError("No module named webview")


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestDesktopNativeCli(unittest.TestCase):
    def test_default_provider_matches_packaged_desktop_default(self) -> None:
        with patch.dict(os.environ, {}, clear=True), patch.object(sys, "frozen", True, create=True):
            args = desktop_native.parse_args([])

        self.assertEqual(args.provider, "ankiconnect")

    def test_parse_args_accepts_native_options(self) -> None:
        args = desktop_native.parse_args([
            "--provider",
            "ankiconnect",
            "--host",
            "127.0.0.1",
            "--port",
            "8760",
            "--ankiconnect-url",
            "http://127.0.0.1:18765",
            "--fallback-browser",
        ])

        self.assertEqual(args.provider, "ankiconnect")
        self.assertEqual(args.host, "127.0.0.1")
        self.assertEqual(args.port, 8760)
        self.assertEqual(args.ankiconnect_url, "http://127.0.0.1:18765")
        self.assertTrue(args.fallback_browser)

    def test_pywebview_present_creates_window_and_starts(self) -> None:
        server_started = threading.Event()
        server_calls: list[tuple[str, int]] = []

        def server_runner(host: str, port: int) -> None:
            server_calls.append((host, port))
            server_started.set()

        webview = SimpleNamespace(
            create_window=MagicMock(),
            start=MagicMock(side_effect=lambda: server_started.wait(1)),
        )

        exit_code = desktop_native.run_native(
            ["--provider", "mock", "--host", "127.0.0.1", "--port", "8760"],
            server_runner=server_runner,
            pywebview_loader=lambda: webview,
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(server_calls, [("127.0.0.1", 8760)])
        webview.create_window.assert_called_once_with(
            "Daily AI Reading Reinforcement",
            "http://127.0.0.1:8760",
        )
        webview.start.assert_called_once_with()

    def test_pywebview_missing_returns_clear_error(self) -> None:
        stderr = StringIO()
        server_runner = MagicMock()

        with patch.dict(os.environ, {}, clear=True):
            exit_code = desktop_native.run_native(
                ["--provider", "mock"],
                server_runner=server_runner,
                pywebview_loader=_raise_import_error,
                stderr=stderr,
            )

        self.assertEqual(exit_code, 1)
        self.assertIn(
            "pywebview is not installed. Use python3 desktop_app.py --provider mock instead.",
            stderr.getvalue(),
        )
        self.assertNotIn("Traceback", stderr.getvalue())
        server_runner.assert_not_called()

    def test_fallback_browser_uses_dependency_free_launcher(self) -> None:
        fallback_runner = MagicMock(return_value=0)
        server_runner = MagicMock()

        exit_code = desktop_native.run_native(
            [
                "--provider",
                "ankiconnect",
                "--host",
                "127.0.0.1",
                "--port",
                "8760",
                "--ankiconnect-url",
                "http://127.0.0.1:18765",
                "--fallback-browser",
            ],
            server_runner=server_runner,
            pywebview_loader=_raise_import_error,
            fallback_runner=fallback_runner,
        )

        self.assertEqual(exit_code, 0)
        fallback_runner.assert_called_once_with([
            "--provider",
            "ankiconnect",
            "--host",
            "127.0.0.1",
            "--port",
            "8760",
            "--ankiconnect-url",
            "http://127.0.0.1:18765",
        ])
        server_runner.assert_not_called()

    def test_provider_and_ankiconnect_url_are_written_to_environment(self) -> None:
        server_started = threading.Event()
        seen_env: dict[str, str | None] = {}

        def server_runner(host: str, port: int) -> None:
            seen_env["provider"] = os.environ.get("DAIRR_DESKTOP_PROVIDER")
            seen_env["ankiconnect_url"] = os.environ.get("DAIRR_ANKICONNECT_URL")
            seen_env["host"] = host
            seen_env["port"] = str(port)
            server_started.set()

        webview = SimpleNamespace(
            create_window=MagicMock(),
            start=MagicMock(side_effect=lambda: server_started.wait(1)),
        )

        with patch.dict(os.environ, {}, clear=True):
            exit_code = desktop_native.run_native(
                [
                    "--provider",
                    "ankiconnect",
                    "--ankiconnect-url",
                    "http://127.0.0.1:18765",
                ],
                server_runner=server_runner,
                pywebview_loader=lambda: webview,
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(seen_env["provider"], "ankiconnect")
        self.assertEqual(seen_env["ankiconnect_url"], "http://127.0.0.1:18765")
        self.assertEqual(seen_env["host"], "127.0.0.1")
        self.assertEqual(seen_env["port"], "8755")

    def test_importing_desktop_native_does_not_start_server_or_gui(self) -> None:
        fake_webview = SimpleNamespace(
            create_window=MagicMock(),
            start=MagicMock(),
        )

        with patch.dict(sys.modules, {"webview": fake_webview}):
            mod = _load_module("dairr_desktop_native_import_probe", _repo_root / "desktop_native.py")

        self.assertTrue(hasattr(mod, "run_native"))
        fake_webview.create_window.assert_not_called()
        fake_webview.start.assert_not_called()


if __name__ == "__main__":
    unittest.main()
