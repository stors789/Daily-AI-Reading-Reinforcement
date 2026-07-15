"""Pure revlog queries used by the Anki add-on adapter."""

from __future__ import annotations

from typing import Any


def fetch_today_review_event_rows(
    db: Any, start_ms: int, end_ms: int
) -> list[tuple[int, int, int, int]]:
    """Return ordered, timestamped current-day answers per physical card.

    The tuple is ``(deck_id, card_id, reviewed_at_ms, ease)``.  Unlike the
    legacy aggregate below, repeated ratings are intentionally preserved and
    sibling cards sharing a note remain distinct.  The caller supplies Anki's
    authoritative scheduler-day bounds.
    """

    return db.all(
        """
        select
            case when c.odid != 0 then c.odid else c.did end as deck_id,
            r.cid,
            r.id as reviewed_at_ms,
            r.ease
        from revlog r
        join cards c on c.id = r.cid
        where r.id >= ? and r.id < ?
        and r.ease between 1 and 4
        and (r.type < 3 or r.factor != 0)
        order by r.id, r.cid
        """,
        start_ms,
        end_ms,
    )


def fetch_today_review_rows(
    db: Any, start_ms: int, end_ms: int
) -> list[tuple[int, int, int, int, int, str]]:
    """Return real card answers in Anki's current study day.

    Anki also writes revlog rows for manual scheduling, rescheduling, and
    filtered-deck previews.  Those rows have no user rating and must not count
    as reviews or prevent a genuinely new card from being marked as new.
    """

    return db.all(
        """
        select
            case when c.odid != 0 then c.odid else c.did end as deck_id,
            r.cid,
            max(case when r.ease = 1 then 1 else 0 end) as failed_today,
            max(
                case
                    when r.type = 0
                    and not exists (
                        select 1 from revlog old
                        where old.cid = r.cid
                        and old.id < ?
                        and old.ease > 0
                        and (old.type < 3 or old.factor != 0)
                    )
                    then 1
                    else 0
                end
            ) as new_today,
            count(*) as review_count,
            group_concat(distinct r.ease) as response_grades
        from revlog r
        join cards c on c.id = r.cid
        where r.id >= ? and r.id < ?
        and r.ease > 0
        and (r.type < 3 or r.factor != 0)
        group by deck_id, r.cid
        order by deck_id, failed_today desc, new_today desc, r.cid
        """,
        start_ms,
        start_ms,
        end_ms,
    )


def parse_response_grades(raw_grades: Any) -> list[int]:
    """Normalize SQLite's grouped ratings to sorted Anki ease values."""

    if raw_grades is None:
        return []
    if isinstance(raw_grades, str):
        values = raw_grades.split(",")
    elif isinstance(raw_grades, (list, tuple, set)):
        values = raw_grades
    else:
        values = [raw_grades]

    grades: set[int] = set()
    for value in values:
        try:
            grade = int(value)
        except (TypeError, ValueError):
            continue
        if 1 <= grade <= 4:
            grades.add(grade)
    return sorted(grades)


def first_response_for_grades(grades: list[int]) -> str | None:
    """Return the compatibility response name for the lowest rating."""

    response_names = {
        1: "FORGET",
        2: "VAGUE",
        3: "FAMILIAR",
        4: "RECOGNIZE",
    }
    return response_names.get(min(grades)) if grades else None
