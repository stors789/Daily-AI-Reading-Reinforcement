"""PyInstaller packaging script for the DAIRR Tauri sidecar backend.

This generates an onedir runtime that Tauri bundles as an application
resource and launches directly from the installed resource directory.

  apps/desktop/src-tauri/binaries/dairr-backend/dairr-backend

The sidecar exposes the same CLI as desktop_app.py:

  dairr-backend --provider ankiconnect --host 127.0.0.1 --port 8755 --no-browser

Usage (from repo root):

  python3 package_tauri_sidecar.py                  # macOS ARM64
  python3 package_tauri_sidecar.py --target-triple x86_64-pc-windows-msvc  # on Windows x64
  python3 package_tauri_sidecar.py --target-triple x86_64-apple-darwin     # on macOS Intel

Output is the target-native onedir runtime under
apps/desktop/src-tauri/binaries/dairr-backend/.  PyInstaller does not
cross-compile: a non-dry-run target must exactly match the current host.
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
SIDECAR_BINARIES_DIR = ROOT / "apps" / "desktop" / "src-tauri" / "binaries"
SIDECAR_RUNTIME_DIR = SIDECAR_BINARIES_DIR / "dairr-backend"
SIDECAR_RUNTIME_KEEPFILE = SIDECAR_RUNTIME_DIR / ".gitkeep"
ENTRY_POINT = ROOT / "desktop_app.py"

TARGET_TRIPLES = frozenset({
    "aarch64-apple-darwin",
    "x86_64-apple-darwin",
    "x86_64-pc-windows-msvc",
})

DESKTOP_MOCK_FILES = (
    "ankiconnect_card_saver.py",
    "ankiconnect_data_adapter.py",
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

CORE_SOURCE_DIR = ROOT / "packages" / "dairr_core" / "src" / "dairr_core"
WEB_SOURCE_DIR = ROOT / "addon" / "daily_ai_reading_reinforcement" / "web"
WEB_ASSET_SUFFIXES = frozenset({".css", ".html", ".js", ".svg", ".png", ".ico", ".webp"})
DATA_PATHS = tuple(
    (source, Path("dairr_core"))
    for source in sorted(CORE_SOURCE_DIR.glob("*.py"))
) + tuple(
    (source, Path("addon/daily_ai_reading_reinforcement/web") / source.relative_to(WEB_SOURCE_DIR).parent)
    for source in sorted(WEB_SOURCE_DIR.rglob("*"))
    if source.is_file() and source.suffix.lower() in WEB_ASSET_SUFFIXES
) + tuple(
    (ROOT / "desktop_mock" / filename, Path("desktop_mock"))
    for filename in DESKTOP_MOCK_FILES
)

# desktop_mock / dairr_core are shipped as data and loaded at runtime, so
# PyInstaller will not see their imports unless they are listed here.
HIDDEN_IMPORTS = (
    "argparse",
    "concurrent.futures",
    "copy",
    "dataclasses",
    "datetime",
    "enum",
    "functools",
    "html",
    "http.server",
    "importlib.util",
    "json",
    "math",
    "pathlib",
    "re",
    "secrets",
    "socket",
    "stat",
    "string",
    "tempfile",
    "threading",
    "time",
    "typing",
    "urllib.error",
    "urllib.parse",
    "urllib.request",
    "uuid",
)

PYINSTALLER_MISSING_MESSAGE = (
    "PyInstaller is not installed. Install it in your packaging environment, "
    "then rerun this command."
)


def detect_target_triple() -> str:
    """Return the target triple for the current platform.

    PyInstaller cross-compilation is not supported, so we can only build
    for the architecture and OS of the current machine.
    """
    import platform as _platform
    machine = _platform.machine().lower()
    system = _platform.system().lower()

    if machine in ("amd64", "x86_64", "x64"):
        arch = "x86_64"
    elif machine in ("aarch64", "arm64"):
        arch = "aarch64"
    else:
        arch = machine or "unknown"

    if system == "darwin":
        return f"{arch}-apple-darwin"
    elif system == "windows":
        return f"{arch}-pc-windows-msvc"
    else:
        return f"{arch}-unknown-linux-gnu"


def sidecar_basename() -> str:
    return "dairr-backend"


def sidecar_runtime_path(target_triple: str) -> Path:
    """Return the executable entry inside the target-native onedir runtime."""
    suffix = ".exe" if target_triple.startswith("x86_64-pc-windows") else ""
    return SIDECAR_RUNTIME_DIR / f"{sidecar_basename()}{suffix}"


def restore_runtime_keepfile() -> None:
    """Keep an otherwise empty runtime directory represented after local builds."""
    SIDECAR_RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    SIDECAR_RUNTIME_KEEPFILE.write_text("\n", encoding="utf-8")


def add_data_separator(platform: str | None = None) -> str:
    current_platform = sys.platform if platform is None else platform
    return ";" if current_platform.startswith("win") else ":"


def format_add_data(source: Path, destination: Path, platform: str | None = None) -> str:
    return f"{source}{add_data_separator(platform)}{destination.as_posix()}"


def build_pyinstaller_command(
    *,
    target_triple: str,
    clean: bool = False,
    pyinstaller: str = "pyinstaller",
    platform: str | None = None,
) -> list[str]:
    """Build a PyInstaller command that produces a fast-starting onedir runtime."""
    name = sidecar_basename()
    command = [
        pyinstaller,
        "--name",
        name,
        "--onedir",
        "--console",
        "--distpath",
        str(SIDECAR_BINARIES_DIR),
        "--workpath",
        str(SIDECAR_BINARIES_DIR / ".build"),
        "--specpath",
        str(SIDECAR_BINARIES_DIR / ".build"),
    ]
    if clean:
        command.append("--clean")
        command.append("--noconfirm")

    for module_name in HIDDEN_IMPORTS:
        command.extend(["--hidden-import", module_name])

    for source, destination in DATA_PATHS:
        command.extend(["--add-data", format_add_data(source, destination, platform)])

    command.append(str(ENTRY_POINT))
    return command


def validate_runtime_entry(binary_path: Path) -> str | None:
    """Return a release-blocking problem for an invalid onedir entry, if any."""
    if not binary_path.is_file():
        return "runtime entry is missing"
    try:
        with open(binary_path, "rb") as f:
            header = f.read(128)
    except OSError:
        return "runtime entry cannot be read"
    if binary_path.stat().st_size < 512:
        return "runtime entry is too small to be a PyInstaller executable"
    if header.startswith(b"#!"):
        return "runtime entry is a script rather than a PyInstaller executable"
    return None


def target_mismatch(target_triple: str, native_target_triple: str | None = None) -> str | None:
    """Describe why a real build target cannot run on this host."""
    native = native_target_triple or detect_target_triple()
    if target_triple not in TARGET_TRIPLES:
        return f"unsupported release target {target_triple!r}"
    if native != target_triple:
        return (
            f"requested target {target_triple!r} does not match native host {native!r}; "
            "PyInstaller cross-compilation is not supported"
        )
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a Tauri sidecar binary for DAIRR desktop.",
    )
    parser.add_argument(
        "--target-triple",
        default=detect_target_triple(),
        help="Native release target (default: auto-detect current platform).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the PyInstaller command without executing it.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Pass --clean --noconfirm to PyInstaller.",
    )
    parser.add_argument(
        "--check-runtime",
        action="store_true",
        help="Validate the target-native onedir runtime entry.",
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
    native_target_triple: str | None = None,
) -> int:
    args = parse_args(argv)
    out = stdout or sys.stdout
    err = stderr or sys.stderr

    target_triple = args.target_triple
    output_path = sidecar_runtime_path(target_triple)

    if target_triple not in TARGET_TRIPLES:
        print(f"ERROR: unsupported release target {target_triple!r}", file=err)
        return 1

    if not args.dry_run:
        mismatch = target_mismatch(target_triple, native_target_triple)
        if mismatch is not None:
            print(f"ERROR: {mismatch}", file=err)
            return 1

    if args.check_runtime:
        problem = validate_runtime_entry(output_path)
        if problem is not None:
            print(f"ERROR: {problem}: {output_path}", file=err)
            return 1
        print(
            f"OK: onedir runtime entry {output_path} "
            f"({output_path.stat().st_size} bytes).",
            file=out,
        )
        return 0

    command = build_pyinstaller_command(
        target_triple=target_triple,
        clean=args.clean,
    )

    if args.dry_run:
        native = native_target_triple or detect_target_triple()
        if target_triple != native:
            print(
                f"PORTABLE DRY RUN ONLY: command targets {target_triple}; "
                f"native host is {native}. No artifact will be produced.",
                file=out,
            )
        print(shlex.join(command), file=out)
        return 0

    if which is None:
        which = shutil.which
    pyinstaller = which("pyinstaller")
    if not pyinstaller:
        print(PYINSTALLER_MISSING_MESSAGE, file=err)
        return 1

    command[0] = pyinstaller

    print(f"Building sidecar for {target_triple} -> {output_path}", file=out)
    print(f"Command: {shlex.join(command)}", file=out)

    if subprocess_run is None:
        subprocess_run = subprocess.run
    result = subprocess_run(command, check=False)
    restore_runtime_keepfile()
    if result.returncode != 0:
        print(f"PyInstaller exited with code {result.returncode}", file=err)
        return int(result.returncode)

    # Verify the output
    if not output_path.is_file():
        print(f"ERROR: sidecar was not created at {output_path}", file=err)
        return 1

    problem = validate_runtime_entry(output_path)
    if problem is not None:
        print(f"ERROR: {problem}: {output_path}", file=err)
        return 1

    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"Sidecar built: {output_path} ({size_mb:.1f} MB)", file=out)
    return 0


def main() -> None:
    raise SystemExit(run_packager())


if __name__ == "__main__":
    main()
