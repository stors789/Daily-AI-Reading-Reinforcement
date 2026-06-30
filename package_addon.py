from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parent
ADDON_DIR = ROOT / "addon" / "daily_ai_reading_reinforcement"
DIST_DIR = ROOT / "dist"
OUT_FILE = DIST_DIR / "daily_ai_reading_reinforcement.ankiaddon"
EXCLUDED_DIRS = {"__pycache__", "user_files"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def main() -> None:
    DIST_DIR.mkdir(exist_ok=True)
    if OUT_FILE.exists():
        OUT_FILE.unlink()

    with ZipFile(OUT_FILE, "w", ZIP_DEFLATED) as archive:
        for path in sorted(ADDON_DIR.rglob("*")):
            relative = path.relative_to(ADDON_DIR)
            if any(part in EXCLUDED_DIRS for part in relative.parts):
                continue
            if path.suffix in EXCLUDED_SUFFIXES:
                continue
            if path.is_file():
                archive.write(path, relative)

    print(f"Wrote {OUT_FILE}")


if __name__ == "__main__":
    main()
