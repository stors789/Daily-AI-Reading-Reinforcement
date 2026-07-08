"""Desktop user-data paths for standalone DAIRR mode.

This module is pure standard library and must not import Anki/aqt modules.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Mapping


def _home_path(home: str | Path | None = None) -> Path:
    if home is not None:
        return Path(home).expanduser()
    return Path.home()


def _app_data_root(
    *,
    home: str | Path | None = None,
    environ: Mapping[str, str] | None = None,
    platform: str | None = None,
) -> Path:
    env = os.environ if environ is None else environ
    current_platform = sys.platform if platform is None else platform
    home_dir = _home_path(home)

    if current_platform == "darwin":
        return home_dir / "Library" / "Application Support" / "DAIRR"
    if current_platform.startswith("win"):
        appdata = env.get("APPDATA")
        if appdata:
            return Path(appdata) / "DAIRR"
        return home_dir / "AppData" / "Roaming" / "DAIRR"
    return home_dir / ".local" / "share" / "dairr"


def app_config_path(
    *,
    home: str | Path | None = None,
    environ: Mapping[str, str] | None = None,
    platform: str | None = None,
) -> Path:
    """Return the packaged-app default config path."""
    return _app_data_root(home=home, environ=environ, platform=platform) / "config.json"


def app_output_dir(
    *,
    home: str | Path | None = None,
    environ: Mapping[str, str] | None = None,
    platform: str | None = None,
) -> Path:
    """Return the packaged-app default article output directory."""
    return _app_data_root(home=home, environ=environ, platform=platform) / "articles"


def legacy_config_path(*, home: str | Path | None = None) -> Path:
    """Return the pre-packaging desktop config path."""
    return _home_path(home) / ".dairr_config.json"
