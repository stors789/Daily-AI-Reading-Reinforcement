from __future__ import annotations

import logging
from typing import Any

try:
    from aqt import mw
except ImportError:
    mw = None

from .anki_enrichment_source import AnkiLocalEnrichmentSource
from .core.utils import (
    clean_enable_anki_local_enrichment,
    clean_anki_local_enrichment_field_map,
    clean_anki_local_enrichment_search_fields,
    clean_anki_local_enrichment_max_matches_per_term,
)

logger = logging.getLogger(__name__)


def build_anki_enrichment_source(config: dict[str, Any]) -> AnkiLocalEnrichmentSource | None:
    """Build AnkiLocalEnrichmentSource from config, or return None if disabled or collection is unavailable."""
    if not clean_enable_anki_local_enrichment(config.get("enable_anki_local_enrichment")):
        return None

    if mw is None or getattr(mw, "col", None) is None:
        logger.warning("Anki local enrichment is enabled but collection is not available.")
        return None

    field_map = clean_anki_local_enrichment_field_map(config.get("anki_local_enrichment_field_map"))
    search_fields = clean_anki_local_enrichment_search_fields(config.get("anki_local_enrichment_search_fields"))
    max_matches = clean_anki_local_enrichment_max_matches_per_term(config.get("anki_local_enrichment_max_matches_per_term"))

    return AnkiLocalEnrichmentSource(
        collection=mw.col,
        field_map=field_map,
        search_field_names=search_fields,
        max_matches_per_term=max_matches,
    )
