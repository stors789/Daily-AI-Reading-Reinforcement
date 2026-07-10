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
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parent.parent
DESKTOP_DIR = ROOT / "apps" / "desktop"
RELEASE_METADATA_PATH = DESKTOP_DIR / "release.json"
TAURI_CONFIG_PATH = DESKTOP_DIR / "src-tauri" / "tauri.conf.json"
CARGO_TOML_PATH = DESKTOP_DIR / "src-tauri" / "Cargo.toml"
PACKAGE_JSON_PATH = DESKTOP_DIR / "package.json"
PACKAGE_LOCK_PATH = DESKTOP_DIR / "package-lock.json"
SEMVER_RE = re.compile(r"^(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
REQUIRED_TARGETS = ("darwin-aarch64", "darwin-x86_64", "windows-x86_64")


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

    subparsers.add_parser("verify", help="ensure all checked-in desktop versions match")

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
            print(assert_versions_in_sync())
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
