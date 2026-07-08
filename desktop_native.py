"""Optional pywebview native shell for DAIRR desktop mode.

This entry point is intentionally a thin scaffold. It reuses the existing
dependency-free desktop launcher configuration and HTTP server, then opens the
local URL in pywebview when that optional package is available.
"""

from __future__ import annotations

import argparse
import importlib
import sys
import threading
from typing import Any, Callable, Sequence, TextIO

import desktop_app


PYWEBVIEW_MISSING_MESSAGE = (
    "pywebview is not installed. Use python3 desktop_app.py --provider {provider} instead."
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Start the optional DAIRR pywebview native shell.",
    )
    parser.add_argument(
        "--provider",
        choices=desktop_app.PROVIDER_CHOICES,
        default="mock",
        help="Deck provider to use for the desktop server.",
    )
    parser.add_argument(
        "--host",
        default=desktop_app.DEFAULT_HOST,
        help="Host interface for the local desktop server.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=desktop_app.DEFAULT_PORT,
        help="Port for the local desktop server.",
    )
    parser.add_argument(
        "--ankiconnect-url",
        default=None,
        help="AnkiConnect endpoint used when --provider ankiconnect is selected.",
    )
    parser.add_argument(
        "--fallback-browser",
        action="store_true",
        help="Open the dependency-free browser launcher if pywebview is unavailable.",
    )
    return parser


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def _load_pywebview() -> Any:
    return importlib.import_module("webview")


def _server_thread(
    server_runner: Callable[[str, int], None],
    host: str,
    port: int,
) -> threading.Thread:
    thread = threading.Thread(
        target=server_runner,
        args=(host, port),
        name="dairr-desktop-server",
        daemon=True,
    )
    thread.start()
    return thread


def _fallback_argv(args: argparse.Namespace) -> list[str]:
    argv = [
        "--provider",
        args.provider,
        "--host",
        args.host,
        "--port",
        str(args.port),
    ]
    if args.ankiconnect_url:
        argv.extend(["--ankiconnect-url", args.ankiconnect_url])
    return argv


def run_native(
    argv: Sequence[str] | None = None,
    *,
    server_runner: Callable[[str, int], None] | None = None,
    pywebview_loader: Callable[[], Any] | None = None,
    fallback_runner: Callable[[Sequence[str]], int] | None = None,
    stderr: TextIO | None = None,
) -> int:
    args = parse_args(argv)
    desktop_app.configure_environment(args)

    if pywebview_loader is None:
        pywebview_loader = _load_pywebview

    try:
        webview = pywebview_loader()
    except ImportError:
        if args.fallback_browser:
            if fallback_runner is None:
                fallback_runner = desktop_app.run_app
            return fallback_runner(_fallback_argv(args))
        print(
            PYWEBVIEW_MISSING_MESSAGE.format(provider=args.provider),
            file=stderr or sys.stderr,
        )
        return 1

    if server_runner is None:
        server_runner = desktop_app._load_server_runner()

    url = f"http://{args.host}:{args.port}"
    _server_thread(server_runner, args.host, args.port)
    webview.create_window("Daily AI Reading Reinforcement", url)
    webview.start()
    return 0


def main() -> None:
    raise SystemExit(run_native())


if __name__ == "__main__":
    main()
