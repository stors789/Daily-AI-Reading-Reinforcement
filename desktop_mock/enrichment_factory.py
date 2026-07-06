"""Phase 21: Enrichment factory for desktop mock."""

import os
import sys
from pathlib import Path
from typing import Any, Mapping

# Add repo root to sys.path to allow importing from root
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from addon.daily_ai_reading_reinforcement.anki_enrichment_source import AnkiLocalEnrichmentSource
from desktop_mock.enrichment import EnrichmentSource, MockEnrichmentSource, WordEnrichment


def build_enrichment_source(
    environ: Mapping[str, str] | None = None, collection: Any = None
) -> EnrichmentSource | None:
    """Build an enrichment source based on DAIRR_DESKTOP_ENRICHMENT."""
    if environ is None:
        environ = os.environ

    val = environ.get("DAIRR_DESKTOP_ENRICHMENT", "").strip().lower()

    if not val or val in ("none", "disabled"):
        return None

    if val == "mock":
        mock_entries = {
            "example": WordEnrichment(
                phonetic="/ɪɡˈzæmpəl/",
                interpretation="mock interpretation",
                phrase="mock phrase",
                phrase_translation="mock translation",
                source="mock",
            )
        }
        return MockEnrichmentSource(mock_entries)

    if val == "anki_local":
        if collection is None:
            raise ValueError("Anki local enrichment requires a collection.")
        return AnkiLocalEnrichmentSource(collection)

    raise ValueError(f"Unknown desktop enrichment source: {val}")
