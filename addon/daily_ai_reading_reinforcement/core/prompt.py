"""Legacy re-export for :mod:`dairr_core.prompt`."""

try:
    from ..dairr_core.prompt import *  # type: ignore[import-not-found]  # noqa: F403
except ImportError:
    from dairr_core.prompt import *  # noqa: F403
