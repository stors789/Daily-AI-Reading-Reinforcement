import re
from typing import Any
from desktop_mock.enrichment import WordEnrichment, EnrichmentSource

def clean_field_text(value: str) -> str:
    if not value:
        return ""
    # Strip simple HTML tags
    clean = re.sub(r'<[^>]+>', '', value)
    # Compress whitespaces
    clean = re.sub(r'\s+', ' ', clean)
    return clean.strip()

class AnkiLocalEnrichmentSource(EnrichmentSource):
    def __init__(
        self,
        collection: Any,
        field_map: dict[str, list[str]] | None = None,
        search_field_names: list[str] | None = None,
        max_matches_per_term: int = 3,
    ):
        self.col = collection
        self.field_map = field_map or {
            "phonetic": ["Phonetic", "Pronunciation", "音标", "発音"],
            "audio_url": ["Audio", "Sound", "音声", "发音"],
            "interpretation": ["Meaning", "Definition", "释义", "中文", "翻译", "意味"],
            "phrase": ["Example", "Sentence", "例句", "例文"],
            "phrase_translation": ["ExampleTranslation", "SentenceTranslation", "例句翻译", "例文訳"],
        }
        self.search_field_names = search_field_names or ["Front", "Word", "Term", "Expression", "单词", "词条", "表面"]
        self.max_matches_per_term = max_matches_per_term

    def enrich_words(self, terms: list[str]) -> dict[str, WordEnrichment]:
        results: dict[str, WordEnrichment] = {}
        
        # Deduplicate terms while preserving order
        seen = set()
        unique_terms = []
        for t in terms:
            if not t:
                continue
            if t not in seen:
                seen.add(t)
                unique_terms.append(t)
        
        for term in unique_terms:
            try:
                # Escape quotes to prevent query injection
                escaped_term = term.replace('"', '\\"')
                query = f'"{escaped_term}"'
                
                note_ids = self.col.find_notes(query)
                if not note_ids:
                    continue
                
                note_ids_to_check = note_ids[:self.max_matches_per_term]
                
                extracted_data = {}
                for nid in note_ids_to_check:
                    try:
                        note = self.col.get_note(nid)
                    except Exception:
                        continue
                    
                    note_fields = {}
                    if hasattr(note, "items"):
                        note_fields = {k.lower(): v for k, v in note.items()}
                    elif isinstance(note, dict):
                        note_fields = {k.lower(): v for k, v in note.items()}
                    elif hasattr(note, "keys"):
                        note_fields = {k.lower(): note[k] for k in note.keys()}
                    
                    for key, target_field_names in self.field_map.items():
                        if key in extracted_data:
                            continue # already found this data field
                        
                        for tf in target_field_names:
                            if tf.lower() in note_fields:
                                val = note_fields[tf.lower()]
                                clean_val = clean_field_text(val)
                                if clean_val:
                                    extracted_data[key] = clean_val
                                    break # field found for this key
                
                if extracted_data:
                    results[term] = WordEnrichment(
                        phonetic=extracted_data.get("phonetic"),
                        audio_url=extracted_data.get("audio_url"),
                        interpretation=extracted_data.get("interpretation"),
                        phrase=extracted_data.get("phrase"),
                        phrase_translation=extracted_data.get("phrase_translation"),
                        source="anki_local"
                    )
            except Exception:
                # Do not fail other terms if one term search fails
                continue
                
        return results
