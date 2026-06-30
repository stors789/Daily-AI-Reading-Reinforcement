from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parent
ADDON_DIR = ROOT / "addon" / "daily_ai_reading_reinforcement"
DIST_DIR = ROOT / "dist"
OUT_FILE = DIST_DIR / "daily_ai_reading_reinforcement.ankiaddon"


def main() -> None:
    DIST_DIR.mkdir(exist_ok=True)
    if OUT_FILE.exists():
        OUT_FILE.unlink()

    with ZipFile(OUT_FILE, "w", ZIP_DEFLATED) as archive:
        for path in sorted(ADDON_DIR.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(ADDON_DIR))

    print(f"Wrote {OUT_FILE}")


if __name__ == "__main__":
    main()
