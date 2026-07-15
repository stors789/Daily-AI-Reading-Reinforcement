from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parent
ADDON_DIR = ROOT / "addon" / "daily_ai_reading_reinforcement"
CORE_PACKAGE_DIR = ROOT / "packages" / "dairr_core" / "src" / "dairr_core"
DIST_DIR = ROOT / "dist"
OUT_FILE = DIST_DIR / "daily_ai_reading_reinforcement.ankiaddon"
EXCLUDED_DIRS = {"__pycache__"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}
SECRET_CONFIG_NAMES = {
    "api_key",
    "authorization",
    "cookie",
    "momo_api_key",
    "momo_cookie",
    "password",
    "secret",
    "token",
}


def sanitized_config_bytes(path: Path) -> bytes:
    """Return distributable defaults without local credentials."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Add-on config.json must be valid UTF-8 JSON.") from exc
    sanitized = _redact_secrets(payload)
    return (json.dumps(sanitized, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _redact_secrets(value: Any, *, key: str = "") -> Any:
    normalized = key.strip().lower()
    if normalized in SECRET_CONFIG_NAMES or normalized.endswith(("_api_key", "_token", "_secret", "_password", "_cookie")):
        return ""
    if isinstance(value, dict):
        return {name: _redact_secrets(item, key=str(name)) for name, item in value.items()}
    if isinstance(value, list):
        return [_redact_secrets(item) for item in value]
    return value


def main() -> None:
    DIST_DIR.mkdir(exist_ok=True)
    if OUT_FILE.exists():
        OUT_FILE.unlink()

    with ZipFile(OUT_FILE, "w", ZIP_DEFLATED) as archive:
        for path in sorted(ADDON_DIR.rglob("*")):
            relative = path.relative_to(ADDON_DIR)
            if any(part in EXCLUDED_DIRS for part in relative.parts):
                continue
            # Never package private runtime history, practice text, drafts, or
            # future user-owned files. The marker README creates the writable
            # directory without copying any local content into a release.
            if relative.parts and relative.parts[0] == "user_files" and relative != Path("user_files/README.txt"):
                continue
            if path.suffix in EXCLUDED_SUFFIXES:
                continue
            if path.is_file():
                if relative == Path("config.json"):
                    archive.writestr(relative.as_posix(), sanitized_config_bytes(path))
                else:
                    archive.write(path, relative)
        for path in sorted(CORE_PACKAGE_DIR.rglob("*")):
            relative = path.relative_to(CORE_PACKAGE_DIR)
            if any(part in EXCLUDED_DIRS for part in relative.parts):
                continue
            if path.suffix in EXCLUDED_SUFFIXES:
                continue
            if path.is_file():
                archive.write(path, Path("dairr_core") / relative)

    print(f"Wrote {OUT_FILE}")


if __name__ == "__main__":
    main()
