from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
CORE_SRC = ROOT / "packages" / "dairr_core" / "src"
if str(CORE_SRC) not in sys.path:
    sys.path.insert(0, str(CORE_SRC))

from dairr_core.article import apply_article_history_evidence, save_article
from dairr_core.capabilities import Provenance
from dairr_core.study_signals import CardIdentity, CardStudySignals, ObservationStatus


class ArticleReuseEvidenceTests(unittest.TestCase):
    def test_only_actual_usage_is_counted_and_timezone_is_normalized(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            save_article(
                "Deck", [], "[ARTICLE_TITLE]\nT\n[MAIN_ARTICLE]\nAlpha appears.",
                articles_dir=root,
                generation_metadata={
                    "generated_at": "2026-07-15T12:00:00+08:00",
                    "targets": [
                        {"id": "ankiconnect:1", "card_id": "1", "target": "alpha"},
                        {"id": "ankiconnect:2", "card_id": "2", "target": "beta"},
                    ],
                    "target_usage": [{"target_id": "ankiconnect:1", "used": True}],
                    "unused_targets": [{"target_id": "ankiconnect:2"}],
                },
            )
            signals = [
                CardStudySignals(CardIdentity("ankiconnect", "1", "n1"), "alpha"),
                CardStudySignals(CardIdentity("ankiconnect", "2", "n2"), "beta"),
            ]
            enriched = apply_article_history_evidence(
                signals,
                articles_dir=root,
                now=datetime(2026, 7, 16, 4, 0, tzinfo=timezone.utc),
            )

        alpha, beta = enriched
        self.assertEqual(alpha.recent_article_inclusions.value, 1)
        self.assertEqual(alpha.recent_article_inclusions.provenance, Provenance.LOCAL_HISTORY)
        self.assertAlmostEqual(alpha.days_since_last_article_use.value, 1.0)
        self.assertEqual(beta.recent_article_inclusions.value, 0)
        self.assertIs(beta.days_since_last_article_use.status, ObservationStatus.UNAVAILABLE)


if __name__ == "__main__":
    unittest.main()
