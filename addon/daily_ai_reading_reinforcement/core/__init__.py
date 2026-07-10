"""Compatibility namespace for legacy add-on ``core.*`` imports.

New shared code lives in the independently installable :mod:`dairr_core`
package. In a source checkout this adds that package's ``src`` directory to
the ordinary module search path; packaged add-ons vendor ``dairr_core`` next
to their entry point.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _enable_source_package() -> None:
    if importlib.util.find_spec("dairr_core") is not None:
        return
    source_root = Path(__file__).resolve().parents[3] / "packages" / "dairr_core" / "src"
    if source_root.is_dir():
        sys.path.insert(0, str(source_root))


_enable_source_package()
