"""Legacy re-export for :mod:`dairr_core.config`."""

try:
    from ..dairr_core.config import *  # type: ignore[import-not-found]  # noqa: F403
except ImportError:
    from dairr_core.config import *  # noqa: F403
