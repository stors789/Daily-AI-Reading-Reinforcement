"""Legacy re-export for :mod:`dairr_core.rendering`."""

try:
    from ..dairr_core.rendering import *  # type: ignore[import-not-found]  # noqa: F403
except ImportError:
    from dairr_core.rendering import *  # noqa: F403
