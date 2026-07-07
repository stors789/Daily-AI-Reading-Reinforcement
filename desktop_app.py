"""Dependency-free desktop launcher for DAIRR.

This starts the existing desktop HTTP server and optionally opens the system
browser. It intentionally uses only the Python standard library so it can serve
as a conservative standalone entry point before a native shell is introduced.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
import threading
import webbrowser
from pathlib import Path
from typing import Callable, MutableMapping, Sequence


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8755
DEFAULT_ANKICONNECT_URL = "http://127.0.0.1:8765"
PROVIDER_CHOICES = ("mock", "real_momo", "ankiconnect")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Start the DAIRR standalone desktop launcher.",
    )
    parser.add_argument(
        "--provider",
        choices=PROVIDER_CHOICES,
        default="mock",
        help="Deck provider to use for the desktop server.",
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help="Host interface for the local desktop server.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help="Port for the local desktop server.",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Start the server without opening the system browser.",
    )
    parser.add_argument(
        "--ankiconnect-url",
        default=None,
        help="AnkiConnect endpoint used when --provider ankiconnect is selected.",
    )
    return parser


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def configure_environment(
    args: argparse.Namespace,
    environ: MutableMapping[str, str] | None = None,
) -> None:
    if environ is None:
        environ = os.environ
    environ["DAIRR_DESKTOP_PROVIDER"] = args.provider
    if args.ankiconnect_url:
        environ["DAIRR_ANKICONNECT_URL"] = args.ankiconnect_url


def _load_server_runner() -> Callable[[str, int], None]:
    repo_root = Path(__file__).resolve().parent
    mock_dir = repo_root / "desktop_mock"
    if str(mock_dir) not in sys.path:
        sys.path.insert(0, str(mock_dir))

    spec = importlib.util.spec_from_file_location(
        "dairr_desktop_mock_main",
        mock_dir / "main.py",
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load desktop_mock/main.py")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.run_server


def _schedule_browser_open(
    url: str,
    browser_open: Callable[[str], bool],
    delay_seconds: float = 0.5,
) -> threading.Timer:
    timer = threading.Timer(delay_seconds, browser_open, args=(url,))
    timer.daemon = True
    timer.start()
    return timer


def run_app(
    argv: Sequence[str] | None = None,
    *,
    server_runner: Callable[[str, int], None] | None = None,
    browser_open: Callable[[str], bool] | None = None,
) -> None:
    args = parse_args(argv)
    configure_environment(args)
    url = f"http://{args.host}:{args.port}"

    if browser_open is None:
        browser_open = webbrowser.open
    if server_runner is None:
        server_runner = _load_server_runner()

    if not args.no_browser:
        _schedule_browser_open(url, browser_open)

    server_runner(args.host, args.port)


def main() -> None:
    run_app()


if __name__ == "__main__":
    main()
