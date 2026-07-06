"""Phase 19: Enrichment source abstraction and mock implementation."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class WordEnrichment:
    phonetic: str | None = None
    audio_url: str | None = None
    interpretation: str | None = None
    phrase: str | None = None
    phrase_translation: str | None = None
    source: str | None = None


class EnrichmentSource(Protocol):
    def enrich_words(self, terms: list[str]) -> dict[str, WordEnrichment]:
        ...


class MockEnrichmentSource:
    def __init__(self, entries: dict[str, WordEnrichment] | None = None):
        self.entries = entries or {}

    def enrich_words(self, terms: list[str]) -> dict[str, WordEnrichment]:
        result = {}
        for term in terms:
            if not term:
                continue
            if term in self.entries:
                result[term] = self.entries[term]
        return result
