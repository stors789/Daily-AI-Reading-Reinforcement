"""Legacy re-export for :mod:`dairr_core.utils`."""

try:
    from ..dairr_core.utils import *  # type: ignore[import-not-found]  # noqa: F403
except ImportError:
    from dairr_core.utils import *  # noqa: F403
