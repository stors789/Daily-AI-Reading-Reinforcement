"""Regression tests for the Anki add-on's direct revlog query."""

from __future__ import annotations

import importlib.util
import sqlite3
import unittest
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parent.parent
    / "addon"
    / "daily_ai_reading_reinforcement"
    / "anki_review_history.py"
)
SPEC = importlib.util.spec_from_file_location("anki_review_history", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
fetch_today_review_rows = MODULE.fetch_today_review_rows
fetch_today_review_event_rows = MODULE.fetch_today_review_event_rows
first_response_for_grades = MODULE.first_response_for_grades
parse_response_grades = MODULE.parse_response_grades


class _AnkiDb:
    def __init__(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.connection.executescript(
            """
            create table cards (id integer primary key, did integer, odid integer);
            create table revlog (
                id integer primary key,
                cid integer,
                ease integer,
                factor integer,
                type integer
            );
            """
        )

    def all(self, sql: str, *args: int) -> list[tuple[int, ...]]:
        return self.connection.execute(sql, args).fetchall()


class AnkiReviewHistoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = _AnkiDb()
        self.db.connection.executemany(
            "insert into cards values (?, ?, ?)",
            [(cid, 10, 0) for cid in range(1, 7)],
        )

    def tearDown(self) -> None:
        self.db.connection.close()

    def _review(
        self, row_id: int, cid: int, ease: int, review_type: int, factor: int = 2500
    ) -> None:
        self.db.connection.execute(
            "insert into revlog values (?, ?, ?, ?, ?)",
            (row_id, cid, ease, factor, review_type),
        )

    def test_returns_all_real_answers_and_classifies_new_and_failed_cards(self) -> None:
        # Correctly answered mature cards must remain candidates.
        self._review(1100, 1, 3, 1)
        self._review(1200, 1, 4, 1)
        # A reset row is not a prior answer and must not hide a new card.
        self._review(500, 2, 0, 4, factor=0)
        self._review(1300, 2, 3, 0)
        # A genuine prior answer means a learning answer today is not new.
        self._review(600, 3, 3, 1)
        self._review(1400, 3, 3, 0)
        self._review(1500, 4, 1, 2)

        rows = fetch_today_review_rows(self.db, 1000, 2000)
        by_card = {row[1]: row for row in rows}

        self.assertEqual(by_card[1][:5], (10, 1, 0, 0, 2))
        self.assertEqual(parse_response_grades(by_card[1][5]), [3, 4])
        self.assertEqual(by_card[2][:5], (10, 2, 0, 1, 1))
        self.assertEqual(parse_response_grades(by_card[2][5]), [3])
        self.assertEqual(by_card[3][:5], (10, 3, 0, 0, 1))
        self.assertEqual(parse_response_grades(by_card[3][5]), [3])
        self.assertEqual(by_card[4][:5], (10, 4, 1, 0, 1))
        self.assertEqual(parse_response_grades(by_card[4][5]), [1])

    def test_ignores_non_answer_revlog_rows(self) -> None:
        # Filtered preview without rescheduling, manual reset, and reschedule.
        self._review(1100, 1, 2, 3, factor=0)
        self._review(1200, 2, 0, 4, factor=0)
        self._review(1300, 3, 0, 5, factor=0)

        self.assertEqual(fetch_today_review_rows(self.db, 1000, 2000), [])

    def test_uses_original_deck_for_filtered_cards(self) -> None:
        self.db.connection.execute("update cards set did = 99, odid = 10 where id = 5")
        self._review(1100, 5, 3, 3, factor=2500)

        self.assertEqual(
            fetch_today_review_rows(self.db, 1000, 2000),
            [(10, 5, 0, 0, 1, "3")],
        )

    def test_vague_rating_is_exposed_to_the_frontend(self) -> None:
        self._review(1100, 6, 2, 1)
        self._review(1200, 6, 3, 1)

        row = fetch_today_review_rows(self.db, 1000, 2000)[0]
        grades = parse_response_grades(row[5])

        self.assertEqual(grades, [2, 3])
        self.assertEqual(first_response_for_grades(grades), "VAGUE")

    def test_event_rows_preserve_timestamp_order_repeats_and_card_identity(self) -> None:
        self.db.connection.execute("update cards set did = 99, odid = 10 where id = 2")
        self._review(1300, 1, 1, 1)
        self._review(1100, 2, 2, 1)
        self._review(1200, 1, 1, 1)
        self._review(1400, 1, 3, 1)
        self._review(1500, 2, 0, 4, factor=0)

        self.assertEqual(
            fetch_today_review_event_rows(self.db, 1000, 2000),
            [
                (10, 2, 1100, 2),
                (10, 1, 1200, 1),
                (10, 1, 1300, 1),
                (10, 1, 1400, 3),
            ],
        )


if __name__ == "__main__":
    unittest.main()
