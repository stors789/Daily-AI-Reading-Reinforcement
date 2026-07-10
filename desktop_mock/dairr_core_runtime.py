"""Make the independently packaged DAIRR core available to desktop hosts.

This is a small development/packaging bootstrap only. It uses the regular
Python import system; no module finder, virtual package, or custom loader is
installed.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def enable_dairr_core_imports() -> None:
    """Add the source or frozen-app parent directory when necessary."""
    if importlib.util.find_spec("dairr_core") is not None:
        return

    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        candidate = Path(frozen_root)
    else:
        candidate = (
            Path(__file__).resolve().parent.parent
            / "packages"
            / "dairr_core"
            / "src"
        )

    if (candidate / "dairr_core").is_dir() and str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))
