"""PyInstaller packaging scaffold for DAIRR desktop entry points.

This script intentionally does not install PyInstaller or optional native-shell
dependencies. It only standardizes the command future packaging environments
can run.
"""

from __future__ import annotations

import argparse
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, Sequence, TextIO


ROOT = Path(__file__).resolve().parent
ENTRY_POINTS = {
    "browser": ROOT / "desktop_app.py",
    "native": ROOT / "desktop_native.py",
}
DESKTOP_MOCK_FILES = (
    "ankiconnect_card_saver.py",
    "ankiconnect_provider.py",
    "desktop_adapters.py",
    "dairr_core_runtime.py",
    "desktop_paths.py",
    "diagnostics.py",
    "learning_sources.py",
    "main.py",
    "mock_data.py",
    "momo_provider.py",
    "real_momo_provider.py",
)
DATA_PATHS = (
    (ROOT / "packages" / "dairr_core" / "src" / "dairr_core", Path("dairr_core")),
    (ROOT / "addon" / "daily_ai_reading_reinforcement" / "web", Path("addon/daily_ai_reading_reinforcement/web")),
) + tuple(
    (ROOT / "desktop_mock" / filename, Path("desktop_mock"))
    for filename in DESKTOP_MOCK_FILES
)
HIDDEN_IMPORTS = (
    "datetime",
    "http.server",
    "urllib.error",
    "urllib.request",
    "uuid",
    "webview",
)
PYINSTALLER_MISSING_MESSAGE = (
    "PyInstaller is not installed. Install it in your packaging environment, "
    "then rerun this command."
)


def add_data_separator(platform: str | None = None) -> str:
    current_platform = sys.platform if platform is None else platform
    return ";" if current_platform.startswith("win") else ":"


def format_add_data(source: Path, destination: Path, platform: str | None = None) -> str:
    return f"{source}{add_data_separator(platform)}{destination.as_posix()}"


def build_pyinstaller_command(
    *,
    entry: str,
    name: str,
    onefile: bool = False,
    windowed: bool = False,
    clean: bool = False,
    icon: str | None = None,
    pyinstaller: str = "pyinstaller",
    platform: str | None = None,
) -> list[str]:
    command = [
        pyinstaller,
        "--name",
        name,
    ]
    if onefile:
        command.append("--onefile")
    if windowed:
        command.append("--windowed")
    if clean:
        command.append("--clean")
        command.append("--noconfirm")
    if icon:
        command.extend(["--icon", icon])

    for module_name in HIDDEN_IMPORTS:
        command.extend(["--hidden-import", module_name])

    for source, destination in DATA_PATHS:
        command.extend(["--add-data", format_add_data(source, destination, platform)])

    command.append(str(ENTRY_POINTS[entry]))
    return command


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a PyInstaller command for DAIRR desktop packaging.",
    )
    parser.add_argument(
        "--entry",
        choices=sorted(ENTRY_POINTS),
        default="browser",
        help="Desktop entry point to package.",
    )
    parser.add_argument(
        "--name",
        default="DAIRR",
        help="Application name passed to PyInstaller.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the PyInstaller command without checking or executing it.",
    )
    parser.add_argument(
        "--onefile",
        action="store_true",
        help="Pass --onefile to PyInstaller.",
    )
    parser.add_argument(
        "--windowed",
        action="store_true",
        help="Pass --windowed to PyInstaller.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Pass --clean to PyInstaller.",
    )
    parser.add_argument(
        "--icon",
        help="Path to the app icon (.icns on macOS, .ico on Windows).",
    )
    return parser


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def run_packager(
    argv: Sequence[str] | None = None,
    *,
    which: Callable[[str], str | None] | None = None,
    subprocess_run: Callable[..., subprocess.CompletedProcess] | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    args = parse_args(argv)
    out = stdout or sys.stdout
    err = stderr or sys.stderr

    icon = args.icon
    if not icon:
        if sys.platform == "darwin":
            default_icns = ROOT / "assets" / "branding" / "icon.icns"
            if default_icns.exists():
                icon = str(default_icns)
        elif sys.platform.startswith("win"):
            default_ico = ROOT / "assets" / "branding" / "icon.ico"
            if default_ico.exists():
                icon = str(default_ico)

    command = build_pyinstaller_command(
        entry=args.entry,
        name=args.name,
        onefile=args.onefile,
        windowed=args.windowed,
        clean=args.clean,
        icon=icon,
    )

    if args.dry_run:
        print(shlex.join(command), file=out)
        return 0

    if which is None:
        which = shutil.which
    pyinstaller = which("pyinstaller")
    if not pyinstaller:
        print(PYINSTALLER_MISSING_MESSAGE, file=err)
        return 1

    command[0] = pyinstaller
    if subprocess_run is None:
        subprocess_run = subprocess.run
    result = subprocess_run(command, check=False)
    return int(result.returncode)


def main() -> None:
    raise SystemExit(run_packager())


if __name__ == "__main__":
    main()
