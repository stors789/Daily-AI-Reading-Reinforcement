#!/usr/bin/env python3
"""Prepare, validate, and stage signed DAIRR desktop releases.

The checked-in ``apps/desktop/release.json`` is the single source of truth for
the desktop product version and updater endpoint.  CI changes its version to
the signed ``vX.Y.Z`` tag before it builds, then produces a short-lived Tauri
configuration containing the updater public key supplied through GitHub
Secrets.  The private signing key is never written to the repository.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parent.parent
DESKTOP_DIR = ROOT / "apps" / "desktop"
RELEASE_METADATA_PATH = DESKTOP_DIR / "release.json"
TAURI_CONFIG_PATH = DESKTOP_DIR / "src-tauri" / "tauri.conf.json"
CARGO_TOML_PATH = DESKTOP_DIR / "src-tauri" / "Cargo.toml"
CARGO_LOCK_PATH = DESKTOP_DIR / "src-tauri" / "Cargo.lock"
PACKAGE_JSON_PATH = DESKTOP_DIR / "package.json"
PACKAGE_LOCK_PATH = DESKTOP_DIR / "package-lock.json"
SEMVER_RE = re.compile(r"^(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
REQUIRED_TARGETS = ("darwin-aarch64", "darwin-x86_64", "windows-x86_64")
WEB_APP_PATH = ROOT / "addon" / "daily_ai_reading_reinforcement" / "web" / "app.js"
ANDROID_VALIDATOR_PATH = ROOT / "apps" / "android" / "tests" / "validate_scaffold.py"
SIDECAR_SCRIPT_PATH = ROOT / "package_tauri_sidecar.py"
DESKTOP_PACKAGE_SCRIPT_PATH = ROOT / "package_desktop.py"


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def validate_version(version: str) -> str:
    value = version.removeprefix("v")
    if not SEMVER_RE.fullmatch(value):
        raise ValueError(f"{version!r} is not a valid SemVer release version")
    return value


def version_from_tag(tag: str) -> str:
    return validate_version(tag)


def metadata() -> dict[str, Any]:
    value = read_json(RELEASE_METADATA_PATH)
    value["version"] = validate_version(str(value.get("version", "")))
    endpoint = value.get("updater_endpoint")
    if not isinstance(endpoint, str) or not endpoint.startswith("https://"):
        raise ValueError("release.json updater_endpoint must use HTTPS")
    return value


def cargo_version() -> str:
    content = CARGO_TOML_PATH.read_text(encoding="utf-8")
    match = re.search(r"(?m)^version\s*=\s*\"([^\"]+)\"\s*$", content)
    if match is None:
        raise ValueError("Cargo.toml does not have a package version")
    return match.group(1)


def set_cargo_version(version: str) -> None:
    content = CARGO_TOML_PATH.read_text(encoding="utf-8")
    updated, count = re.subn(
        r"(?m)^version\s*=\s*\"[^\"]+\"\s*$",
        f'version = "{version}"',
        content,
        count=1,
    )
    if count != 1:
        raise ValueError("Cargo.toml does not have exactly one package version")
    CARGO_TOML_PATH.write_text(updated, encoding="utf-8")


def cargo_lock_version() -> str:
    content = CARGO_LOCK_PATH.read_text(encoding="utf-8")
    match = re.search(
        r'(?ms)^\[\[package\]\]\nname = "dairr-desktop"\nversion = "([^"]+)"$',
        content,
    )
    if match is None:
        raise ValueError("Cargo.lock does not have the dairr-desktop package record")
    return match.group(1)


def set_cargo_lock_version(version: str) -> None:
    content = CARGO_LOCK_PATH.read_text(encoding="utf-8")
    updated, count = re.subn(
        r'(?ms)(^\[\[package\]\]\nname = "dairr-desktop"\nversion = ")[^"]+("$)',
        rf"\g<1>{version}\g<2>",
        content,
        count=1,
    )
    if count != 1:
        raise ValueError("Cargo.lock does not have exactly one dairr-desktop package record")
    CARGO_LOCK_PATH.write_text(updated, encoding="utf-8")


def configured_versions() -> dict[str, str]:
    release = metadata()
    tauri = read_json(TAURI_CONFIG_PATH)
    package = read_json(PACKAGE_JSON_PATH)
    package_lock = read_json(PACKAGE_LOCK_PATH)
    lock_root = package_lock.get("packages", {}).get("", {})
    return {
        "release.json": release["version"],
        "tauri.conf.json": str(tauri.get("version", "")),
        "Cargo.toml": cargo_version(),
        "Cargo.lock": cargo_lock_version(),
        "package.json": str(package.get("version", "")),
        "package-lock.json": str(package_lock.get("version", "")),
        "package-lock root": str(lock_root.get("version", "")),
    }


def assert_versions_in_sync() -> str:
    versions = configured_versions()
    unique = set(versions.values())
    if len(unique) != 1:
        rendered = ", ".join(f"{name}={version}" for name, version in versions.items())
        raise ValueError(f"desktop version metadata is out of sync: {rendered}")
    return next(iter(unique))


def assert_checked_in_release_config_safe() -> str:
    """Validate metadata while ensuring no signing material is checked in."""
    version = assert_versions_in_sync()
    release = metadata()
    tauri = read_json(TAURI_CONFIG_PATH)
    updater = tauri.get("plugins", {}).get("updater", {})
    if updater.get("pubkey") or updater.get("endpoints"):
        raise ValueError("checked-in Tauri updater config must not contain release credentials or endpoints")
    bundle = tauri.get("bundle", {})
    if bundle.get("createUpdaterArtifacts"):
        raise ValueError("checked-in Tauri config must not create unsigned updater artifacts")
    macos = bundle.get("macOS", {})
    windows = bundle.get("windows", {})
    if macos.get("signingIdentity") or windows.get("certificateThumbprint"):
        raise ValueError("checked-in Tauri config must not contain signing identities")
    if bundle.get("resources") != ["binaries/dairr-backend"]:
        raise ValueError("Tauri bundle must contain only the reviewed Python sidecar resource")
    endpoint = str(release["updater_endpoint"])
    if not endpoint.endswith("/releases/latest/download/latest.json"):
        raise ValueError("updater endpoint must target the static latest.json release asset")
    return version


def _import_check_source() -> str:
    return (
        "import importlib,pkgutil,sys;"
        "sys.path.insert(0,'packages/dairr_core/src');"
        "import dairr_core;"
        "[importlib.import_module('dairr_core.'+m.name) for m in pkgutil.iter_modules(dairr_core.__path__)];"
        "import desktop_app,desktop_native;"
        "print('Production import check passed.')"
    )


def pre_publish_checks() -> list[tuple[str, list[str], Path, str | None]]:
    """Return the complete credential-free release gate in execution order."""
    python = sys.executable
    return [
        (
            "Python compile",
            [
                python, "-m", "compileall", "-q",
                "package_desktop.py", "package_tauri_sidecar.py", "scripts", "packages",
                "addon", "desktop_mock", "tests", "desktop_app.py", "desktop_native.py",
            ],
            ROOT,
            None,
        ),
        ("Production imports", [python, "-c", _import_check_source()], ROOT, None),
        ("Full unittest suite", [python, "-m", "unittest", "discover", "-s", "tests", "-v"], ROOT, None),
        (
            "Add-on package privacy",
            [python, "-m", "unittest", "-v", "tests.test_package_addon_release"],
            ROOT,
            None,
        ),
        (
            "Portable web UI static tests",
            [
                python, "-m", "unittest", "-v", "tests.test_web_i18n",
                "tests.test_web_card_interactions", "tests.test_web_release_workbench",
                "tests.test_tauri_app_shell",
            ],
            ROOT,
            None,
        ),
        ("Web JavaScript syntax", ["node", "--check", str(WEB_APP_PATH)], ROOT, "node"),
        ("Android static validator", [python, str(ANDROID_VALIDATOR_PATH)], ROOT, None),
        (
            "Browser desktop package dry-run",
            [python, str(DESKTOP_PACKAGE_SCRIPT_PATH), "--entry", "browser", "--windowed", "--clean", "--dry-run"],
            ROOT,
            None,
        ),
        (
            "Native desktop package dry-run",
            [python, str(DESKTOP_PACKAGE_SCRIPT_PATH), "--entry", "native", "--windowed", "--clean", "--dry-run"],
            ROOT,
            None,
        ),
        (
            "Tauri sidecar package dry-run",
            [python, str(SIDECAR_SCRIPT_PATH), "--dry-run"],
            ROOT,
            None,
        ),
        ("Tauri npm metadata", ["npm", "run", "info"], DESKTOP_DIR, "npm"),
        ("Tauri Cargo check", ["cargo", "check", "--locked"], DESKTOP_DIR / "src-tauri", "cargo"),
    ]


def run_pre_publish_gate(*, allow_missing_tooling: bool = False) -> None:
    version = assert_checked_in_release_config_safe()
    print(f"Verified credential-free desktop release metadata for {version}.")
    for label, command, cwd, tool in pre_publish_checks():
        if tool is not None and shutil.which(tool) is None:
            if allow_missing_tooling:
                print(f"SKIP {label}: {tool} is unavailable")
                continue
            raise ValueError(f"{label} requires {tool} on PATH")
        print(f"\n==> {label}", flush=True)
        result = subprocess.run(command, cwd=cwd, check=False)
        if result.returncode != 0:
            raise ValueError(f"{label} failed with exit code {result.returncode}")
    print("\nPre-publish verification passed.")


def sync_version(version: str) -> None:
    version = validate_version(version)
    release = metadata()
    release["version"] = version
    write_json(RELEASE_METADATA_PATH, release)

    tauri = read_json(TAURI_CONFIG_PATH)
    tauri["version"] = version
    write_json(TAURI_CONFIG_PATH, tauri)

    package = read_json(PACKAGE_JSON_PATH)
    package["version"] = version
    write_json(PACKAGE_JSON_PATH, package)

    package_lock = read_json(PACKAGE_LOCK_PATH)
    package_lock["version"] = version
    packages = package_lock.setdefault("packages", {})
    if not isinstance(packages.get(""), dict):
        raise ValueError("package-lock.json has no root package record")
    packages[""]["version"] = version
    write_json(PACKAGE_LOCK_PATH, package_lock)
    set_cargo_version(version)
    set_cargo_lock_version(version)


def updater_config(
    public_key: str,
    windows_certificate_thumbprint: str,
    windows_timestamp_url: str,
) -> dict[str, Any]:
    if not public_key.strip() or "REPLACE" in public_key.upper():
        raise ValueError("a real Tauri updater public key is required for release builds")
    if not windows_certificate_thumbprint.strip():
        raise ValueError("a Windows certificate thumbprint is required for release builds")
    if not windows_timestamp_url.startswith(("http://", "https://")):
        raise ValueError("a Windows timestamp URL is required for release builds")
    release = metadata()
    return {
        "version": release["version"],
        "bundle": {
            "createUpdaterArtifacts": True,
            "windows": {
                "certificateThumbprint": windows_certificate_thumbprint,
                "digestAlgorithm": "sha256",
                "timestampUrl": windows_timestamp_url,
            },
        },
        "plugins": {
            "updater": {
                "pubkey": public_key,
                "endpoints": [release["updater_endpoint"]],
                "windows": {"installMode": "passive"},
            }
        },
    }


def prepare_config(
    version: str,
    public_key: str,
    windows_certificate_thumbprint: str,
    windows_timestamp_url: str,
    output: Path,
) -> None:
    sync_version(version)
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(
        output,
        updater_config(
            public_key,
            windows_certificate_thumbprint,
            windows_timestamp_url,
        ),
    )


def find_single_artifact(bundle_dir: Path, pattern: str) -> Path:
    candidates = sorted(bundle_dir.glob(pattern))
    if len(candidates) != 1:
        rendered = ", ".join(str(path) for path in candidates) or "none"
        raise ValueError(f"expected one {pattern!r} in {bundle_dir}, found {rendered}")
    return candidates[0]


def collect_artifacts(target: str, bundle_dir: Path, output_dir: Path) -> None:
    if target not in REQUIRED_TARGETS:
        raise ValueError(f"unsupported updater target {target!r}")
    if target.startswith("darwin-"):
        artifact = find_single_artifact(bundle_dir / "macos", "*.app.tar.gz")
        staged_name = f"dairr-{target}.app.tar.gz"
    else:
        artifact = find_single_artifact(bundle_dir / "nsis", "*-setup.exe")
        staged_name = f"dairr-{target}-setup.exe"
    signature = artifact.with_name(f"{artifact.name}.sig")
    if not signature.is_file():
        raise ValueError(f"missing updater signature {signature}")
    output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(artifact, output_dir / staged_name)
    shutil.copy2(signature, output_dir / f"{staged_name}.sig")


def latest_json(version: str, base_url: str, input_dir: Path, output: Path, notes: str) -> None:
    version = validate_version(version)
    if not base_url.startswith("https://"):
        raise ValueError("release asset base URL must use HTTPS")
    platforms: dict[str, dict[str, str]] = {}
    for target in REQUIRED_TARGETS:
        if target.startswith("darwin-"):
            artifact = input_dir / f"dairr-{target}.app.tar.gz"
        else:
            artifact = input_dir / f"dairr-{target}-setup.exe"
        signature = artifact.with_name(f"{artifact.name}.sig")
        if not artifact.is_file() or not signature.is_file():
            raise ValueError(f"missing staged updater artifact or signature for {target}")
        platforms[target] = {
            "url": f"{base_url.rstrip('/')}/{artifact.name}",
            "signature": signature.read_text(encoding="utf-8").strip(),
        }
    write_json(
        output,
        {
            "version": version,
            "notes": notes,
            "pub_date": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "platforms": platforms,
        },
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("verify", help="validate checked-in desktop release metadata")

    pre_publish = subparsers.add_parser(
        "pre-publish",
        help="run the complete credential-free test, static, import, and packaging gate",
    )
    pre_publish.add_argument(
        "--allow-missing-tooling",
        action="store_true",
        help="report and skip unavailable Node/npm/Cargo checks (never used by release CI)",
    )

    sync = subparsers.add_parser("sync-version", help="set all desktop version records")
    sync.add_argument("--version", required=True)

    prepare = subparsers.add_parser("prepare-config", help="generate a non-committed release updater config")
    prepare.add_argument("--version", required=True)
    prepare.add_argument("--updater-public-key", required=True)
    prepare.add_argument("--windows-certificate-thumbprint", required=True)
    prepare.add_argument("--windows-timestamp-url", required=True)
    prepare.add_argument("--output", type=Path, required=True)

    collect = subparsers.add_parser("collect-artifacts", help="stage updater artifacts with stable release names")
    collect.add_argument("--target", choices=REQUIRED_TARGETS, required=True)
    collect.add_argument("--bundle-dir", type=Path, required=True)
    collect.add_argument("--output-dir", type=Path, required=True)

    latest = subparsers.add_parser("latest-json", help="build the static Tauri update manifest")
    latest.add_argument("--version", required=True)
    latest.add_argument("--base-url", required=True)
    latest.add_argument("--input-dir", type=Path, required=True)
    latest.add_argument("--output", type=Path, required=True)
    latest.add_argument("--notes", default="")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "verify":
            print(assert_checked_in_release_config_safe())
        elif args.command == "pre-publish":
            run_pre_publish_gate(allow_missing_tooling=args.allow_missing_tooling)
        elif args.command == "sync-version":
            sync_version(args.version)
            print(assert_versions_in_sync())
        elif args.command == "prepare-config":
            prepare_config(
                args.version,
                args.updater_public_key,
                args.windows_certificate_thumbprint,
                args.windows_timestamp_url,
                args.output,
            )
            print(args.output)
        elif args.command == "collect-artifacts":
            collect_artifacts(args.target, args.bundle_dir, args.output_dir)
        elif args.command == "latest-json":
            latest_json(args.version, args.base_url, args.input_dir, args.output, args.notes)
            print(args.output)
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
