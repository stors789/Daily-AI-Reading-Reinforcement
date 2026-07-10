"""PyInstaller packaging script for the DAIRR Tauri sidecar backend.

This generates an onedir runtime that Tauri bundles as an application
resource.  Unlike PyInstaller onefile mode, it does not unpack itself into a
temporary directory on every launch.

  apps/desktop/src-tauri/binaries/dairr-backend-aarch64-apple-darwin

The sidecar exposes the same CLI as desktop_app.py:

  dairr-backend --provider ankiconnect --host 127.0.0.1 --port 8755 --no-browser

Usage (from repo root):

  python3 package_tauri_sidecar.py                  # macOS ARM64
  python3 package_tauri_sidecar.py --target-triple x86_64-pc-windows-msvc  # Windows
  python3 package_tauri_sidecar.py --target-triple x86_64-apple-darwin     # macOS Intel

Output is written directly into apps/desktop/src-tauri/binaries/,
replacing the placeholder stubs there.
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
ENTRY_POINT = ROOT / "desktop_app.py"

TARGET_TRIPLES = frozenset({
    "aarch64-apple-darwin",
    "x86_64-apple-darwin",
    "x86_64-pc-windows-msvc",
})

DESKTOP_MOCK_FILES = (
    "ankiconnect_card_saver.py",
    "ankiconnect_provider.py",
    "desktop_adapters.py",
    "dairr_core_runtime.py",
    "desktop_paths.py",
    "diagnostics.py",
    "main.py",
    "mock_data.py",
    "momo_provider.py",
    "real_momo_provider.py",
)

DATA_PATHS = (
    (ROOT / "packages" / "dairr_core" / "src" / "dairr_core", Path("dairr_core")),
    (ROOT / "addon" / "daily_ai_reading_reinforcement" / "web",
     Path("addon/daily_ai_reading_reinforcement/web")),
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

    arch = "x86_64" if machine in ("amd64", "x86_64", "x64") else "aarch64"

    if system == "darwin":
        return f"{arch}-apple-darwin"
    elif system == "windows":
        return "x86_64-pc-windows-msvc"
    else:
        return f"{arch}-unknown-linux-gnu"


def sidecar_basename() -> str:
    return "dairr-backend"


def sidecar_filename(target_triple: str) -> str:
    """Return the full sidecar filename for a target triple."""
    base = sidecar_basename()
    if target_triple.startswith("x86_64-pc-windows") or target_triple.endswith("-msvc"):
        return f"{base}-{target_triple}.exe"
    return f"{base}-{target_triple}"


def sidecar_output_path(target_triple: str) -> Path:
    """Full absolute path where the sidecar binary should land."""
    return SIDECAR_BINARIES_DIR / sidecar_filename(target_triple)


def sidecar_runtime_path(target_triple: str) -> Path:
    suffix = ".exe" if target_triple.startswith("x86_64-pc-windows") else ""
    return SIDECAR_RUNTIME_DIR / f"{sidecar_basename()}{suffix}"


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


def is_placeholder(binary_path: Path) -> bool:
    """Check whether a file at binary_path is a placeholder shell script.

    Placeholders are small shell scripts (shebang or echo) that exit 70.
    A real PyInstaller binary is much larger and contains compiled code.
    """
    if not binary_path.is_file():
        return True
    try:
        with open(binary_path, "rb") as f:
            header = f.read(128)
    except OSError:
        return True
    # Placeholder is a short shell script (< 512 bytes) starting with #!
    if binary_path.stat().st_size < 512:
        if header.startswith(b"#!"):
            return True
        # The Windows placeholder is a text file
        try:
            text = header.decode("utf-8", errors="replace")
            if "placeholder" in text.lower():
                return True
        except UnicodeDecodeError:
            pass
    return False


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a Tauri sidecar binary for DAIRR desktop.",
    )
    parser.add_argument(
        "--target-triple",
        default=detect_target_triple(),
        help="Target triple for sidecar naming (default: auto-detect current platform).",
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
        "--check-placeholder",
        action="store_true",
        help="Check whether the current sidecar at the output path is still a placeholder.",
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

    target_triple = args.target_triple
    output_path = sidecar_runtime_path(target_triple)

    if args.check_placeholder:
        if is_placeholder(output_path):
            print(
                f"WARNING: {output_path} is still a placeholder "
                f"- build the real sidecar.",
                file=out,
            )
            return 1
        else:
            print(
                f"OK: {output_path} is a real binary "
                f"({output_path.stat().st_size} bytes).",
                file=out,
            )
            return 0

    command = build_pyinstaller_command(
        target_triple=target_triple,
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

    print(f"Building sidecar for {target_triple} -> {output_path}", file=out)
    print(f"Command: {shlex.join(command)}", file=out)

    if subprocess_run is None:
        subprocess_run = subprocess.run
    result = subprocess_run(command, check=False)
    if result.returncode != 0:
        print(f"PyInstaller exited with code {result.returncode}", file=err)
        return int(result.returncode)

    # Verify the output
    if not output_path.is_file():
        print(f"ERROR: sidecar was not created at {output_path}", file=err)
        return 1

    if is_placeholder(output_path):
        print(f"ERROR: sidecar at {output_path} is still a placeholder", file=err)
        return 1

    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"Sidecar built: {output_path} ({size_mb:.1f} MB)", file=out)
    return 0


def main() -> None:
    raise SystemExit(run_packager())


if __name__ == "__main__":
    main()
