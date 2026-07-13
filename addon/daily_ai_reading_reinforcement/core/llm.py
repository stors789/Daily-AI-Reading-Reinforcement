"""Legacy re-export for :mod:`dairr_core.llm`."""

try:
    from ..dairr_core.llm import *  # type: ignore[import-not-found]  # noqa: F403
except ImportError:
    from dairr_core.llm import *  # noqa: F403
