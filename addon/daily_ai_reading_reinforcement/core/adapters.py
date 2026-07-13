"""Legacy re-export for :mod:`dairr_core.adapters`."""

try:
    from ..dairr_core.adapters import *  # type: ignore[import-not-found]  # noqa: F403
except ImportError:
    from dairr_core.adapters import *  # noqa: F403
