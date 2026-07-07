"""Tests for the dependency-free desktop launcher."""

from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch


_repo_root = Path(__file__).resolve().parent.parent
_mock_dir = _repo_root / "desktop_mock"
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))
if str(_mock_dir) not in sys.path:
    sys.path.insert(0, str(_mock_dir))

import desktop_app


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestDesktopAppCli(unittest.TestCase):
    def test_parse_args_accepts_launcher_options(self) -> None:
        args = desktop_app.parse_args([
            "--provider",
            "ankiconnect",
            "--host",
            "127.0.0.1",
            "--port",
            "8760",
            "--no-browser",
            "--ankiconnect-url",
            "http://127.0.0.1:18765",
        ])

        self.assertEqual(args.provider, "ankiconnect")
        self.assertEqual(args.host, "127.0.0.1")
        self.assertEqual(args.port, 8760)
        self.assertTrue(args.no_browser)
        self.assertEqual(args.ankiconnect_url, "http://127.0.0.1:18765")

    def test_parse_args_accepts_check(self) -> None:
        args = desktop_app.parse_args(["--provider", "ankiconnect", "--check"])

        self.assertTrue(args.check)

    def test_parse_args_accepts_check_write(self) -> None:
        args = desktop_app.parse_args(["--provider", "ankiconnect", "--check-write"])

        self.assertTrue(args.check_write)

    def test_parse_args_rejects_check_write_without_ankiconnect(self) -> None:
        with patch("sys.stderr", StringIO()), self.assertRaises(SystemExit) as ctx:
            desktop_app.parse_args(["--provider", "mock", "--check-write"])

        self.assertEqual(ctx.exception.code, 2)

    def test_help_mentions_check_write_writes_smoke_card(self) -> None:
        help_text = desktop_app.build_parser().format_help()

        self.assertIn("--check-write", help_text)
        self.assertIn("writes one", help_text)
        self.assertIn("DAIRR smoke test article card to local Anki", help_text)

    def test_configure_environment_writes_provider(self) -> None:
        args = desktop_app.parse_args(["--provider", "real_momo"])
        environ: dict[str, str] = {}

        desktop_app.configure_environment(args, environ)

        self.assertEqual(environ["DAIRR_DESKTOP_PROVIDER"], "real_momo")
        self.assertNotIn("DAIRR_ANKICONNECT_URL", environ)

    def test_configure_environment_writes_ankiconnect_url(self) -> None:
        args = desktop_app.parse_args([
            "--provider",
            "ankiconnect",
            "--ankiconnect-url",
            "http://127.0.0.1:18765",
        ])
        environ: dict[str, str] = {}

        desktop_app.configure_environment(args, environ)

        self.assertEqual(environ["DAIRR_DESKTOP_PROVIDER"], "ankiconnect")
        self.assertEqual(environ["DAIRR_ANKICONNECT_URL"], "http://127.0.0.1:18765")

    def test_run_app_no_browser_does_not_open_browser(self) -> None:
        server_runner = MagicMock()

        with patch.dict(os.environ, {}, clear=True), patch("webbrowser.open") as mock_open:
            desktop_app.run_app(
                ["--provider", "mock", "--host", "127.0.0.1", "--port", "8760", "--no-browser"],
                server_runner=server_runner,
            )

        mock_open.assert_not_called()
        server_runner.assert_called_once_with("127.0.0.1", 8760)

    def test_run_app_sets_environment_before_starting_server(self) -> None:
        seen_env: dict[str, str | None] = {}

        def fake_server_runner(host: str, port: int) -> None:
            seen_env["provider"] = os.environ.get("DAIRR_DESKTOP_PROVIDER")
            seen_env["ankiconnect_url"] = os.environ.get("DAIRR_ANKICONNECT_URL")
            seen_env["host"] = host
            seen_env["port"] = str(port)

        with patch.dict(os.environ, {}, clear=True):
            desktop_app.run_app(
                [
                    "--provider",
                    "ankiconnect",
                    "--ankiconnect-url",
                    "http://127.0.0.1:18765",
                    "--no-browser",
                ],
                server_runner=fake_server_runner,
            )

        self.assertEqual(seen_env["provider"], "ankiconnect")
        self.assertEqual(seen_env["ankiconnect_url"], "http://127.0.0.1:18765")
        self.assertEqual(seen_env["host"], "127.0.0.1")
        self.assertEqual(seen_env["port"], "8755")

    def test_run_app_check_does_not_start_server_or_browser(self) -> None:
        server_runner = MagicMock()
        browser_open = MagicMock()
        stdout = StringIO()

        def check_runner(provider, environ):
            return {
                "ok": True,
                "provider": provider,
                "checks": [{"name": "probe", "ok": True, "message": environ["DAIRR_DESKTOP_PROVIDER"]}],
            }

        with patch.dict(os.environ, {}, clear=True):
            exit_code = desktop_app.run_app(
                ["--provider", "mock", "--check"],
                server_runner=server_runner,
                browser_open=browser_open,
                check_runner=check_runner,
                check_formatter=lambda result: f"checked {result['provider']}",
                stdout=stdout,
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(stdout.getvalue().strip(), "checked mock")
        server_runner.assert_not_called()
        browser_open.assert_not_called()

    def test_run_app_check_returns_failure_code(self) -> None:
        stdout = StringIO()

        with patch.dict(os.environ, {}, clear=True):
            exit_code = desktop_app.run_app(
                ["--provider", "ankiconnect", "--check"],
                server_runner=MagicMock(),
                browser_open=MagicMock(),
                check_runner=lambda provider, environ: {"ok": False, "provider": provider, "checks": []},
                check_formatter=lambda result: "failed",
                stdout=stdout,
            )

        self.assertEqual(exit_code, 1)

    def test_run_app_check_write_does_not_start_server_or_browser(self) -> None:
        server_runner = MagicMock()
        browser_open = MagicMock()
        stdout = StringIO()

        def check_write_runner(environ):
            return {
                "ok": True,
                "provider": environ["DAIRR_DESKTOP_PROVIDER"],
                "mode": "write",
                "checks": [{"name": "article note created", "ok": True, "message": "ok"}],
            }

        with patch.dict(os.environ, {}, clear=True):
            exit_code = desktop_app.run_app(
                ["--provider", "ankiconnect", "--check-write"],
                server_runner=server_runner,
                browser_open=browser_open,
                check_write_runner=check_write_runner,
                check_write_formatter=lambda result: f"write checked {result['provider']}",
                stdout=stdout,
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(stdout.getvalue().strip(), "write checked ankiconnect")
        server_runner.assert_not_called()
        browser_open.assert_not_called()


class TestDesktopMockImport(unittest.TestCase):
    def test_importing_main_does_not_start_server(self) -> None:
        with patch("http.server.ThreadingHTTPServer") as mock_server:
            mod = _load_module("dairr_mock_import_probe", _mock_dir / "main.py")

        mock_server.assert_not_called()
        self.assertIsNone(mod.DECK_PROVIDER)


if __name__ == "__main__":
    unittest.main()
