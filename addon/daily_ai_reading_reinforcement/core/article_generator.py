"""Legacy re-export for :mod:`dairr_core.article_generator`."""

try:
    from ..dairr_core.article_generator import *  # type: ignore[import-not-found]  # noqa: F403
except ImportError:
    from dairr_core.article_generator import *  # noqa: F403
