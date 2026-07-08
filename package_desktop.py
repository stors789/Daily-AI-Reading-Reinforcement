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
DATA_PATHS = (
    (ROOT / "addon" / "daily_ai_reading_reinforcement" / "web", Path("addon/daily_ai_reading_reinforcement/web")),
    (ROOT / "desktop_mock", Path("desktop_mock")),
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

    command = build_pyinstaller_command(
        entry=args.entry,
        name=args.name,
        onefile=args.onefile,
        windowed=args.windowed,
        clean=args.clean,
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
