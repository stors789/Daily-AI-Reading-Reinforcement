"""Deterministic, editable segmentation for translation-practice source text.

This module deliberately performs no model calls.  It never truncates input:
callers receive a structured limit error and can ask the user to shorten or
split the text explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import re
from typing import Iterable, Protocol, TypeVar
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class SegmentationLimits:
    max_text_characters: int = 100_000
    max_segments: int = 500
    max_segment_characters: int = 20_000

    def __post_init__(self) -> None:
        if min(self.max_text_characters, self.max_segments, self.max_segment_characters) < 1:
            raise ValueError("segmentation limits must be positive")


class TextLimitExceeded(ValueError):
    """Raised instead of silently truncating source text."""

    def __init__(self, code: str, actual: int, limit: int) -> None:
        self.code = code
        self.actual = actual
        self.limit = limit
        super().__init__(f"{code}: {actual} exceeds the explicit limit of {limit}")


class EditableSegment(Protocol):
    id: str
    position: int
    source_text: str
    reference_text: str | None
    unknown_fields: dict


SegmentT = TypeVar("SegmentT", bound=EditableSegment)


def stable_id() -> str:
    return uuid4().hex


def paragraph_texts(text: str, limits: SegmentationLimits | None = None) -> list[str]:
    """Split on blank lines, preserving single newlines within a paragraph."""

    limits = limits or SegmentationLimits()
    if len(text) > limits.max_text_characters:
        raise TextLimitExceeded("text_too_long", len(text), limits.max_text_characters)
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []
    parts = [part.strip() for part in re.split(r"\n[\t ]*\n+", normalized) if part.strip()]
    if len(parts) > limits.max_segments:
        raise TextLimitExceeded("too_many_segments", len(parts), limits.max_segments)
    for part in parts:
        if len(part) > limits.max_segment_characters:
            raise TextLimitExceeded(
                "segment_too_long", len(part), limits.max_segment_characters
            )
    return parts


def normalize_positions(segments: Iterable[SegmentT]) -> tuple[SegmentT, ...]:
    return tuple(replace(segment, position=index) for index, segment in enumerate(segments))


def _validate_edited(segments: Iterable[SegmentT], limits: SegmentationLimits | None) -> tuple[SegmentT, ...]:
    limits = limits or SegmentationLimits()
    result = normalize_positions(segments)
    if len(result) > limits.max_segments:
        raise TextLimitExceeded("too_many_segments", len(result), limits.max_segments)
    total = sum(len(segment.source_text) for segment in result) + max(0, len(result) - 1) * 2
    if total > limits.max_text_characters:
        raise TextLimitExceeded("text_too_long", total, limits.max_text_characters)
    for segment in result:
        if len(segment.source_text) > limits.max_segment_characters:
            raise TextLimitExceeded(
                "segment_too_long", len(segment.source_text), limits.max_segment_characters
            )
    return result


def update_segment(
    segments: Iterable[SegmentT], segment_id: str, text: str,
    limits: SegmentationLimits | None = None,
) -> tuple[SegmentT, ...]:
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("a practice segment cannot be empty")
    found = False
    result: list[SegmentT] = []
    for segment in segments:
        if segment.id == segment_id:
            result.append(replace(segment, source_text=cleaned))
            found = True
        else:
            result.append(segment)
    if not found:
        raise KeyError(segment_id)
    return _validate_edited(result, limits)


def reorder_segments(segments: Iterable[SegmentT], ordered_ids: Iterable[str]) -> tuple[SegmentT, ...]:
    current = tuple(segments)
    by_id = {segment.id: segment for segment in current}
    ids = tuple(ordered_ids)
    if len(by_id) != len(current):
        raise ValueError("segment ids must be unique")
    if len(ids) != len(current) or len(set(ids)) != len(ids) or set(ids) != set(by_id):
        raise ValueError("ordered_ids must contain every segment id exactly once")
    return normalize_positions(by_id[segment_id] for segment_id in ids)


def split_segment(
    segments: Iterable[SegmentT], segment_id: str, offset: int, *, new_id: str | None = None,
    limits: SegmentationLimits | None = None,
) -> tuple[SegmentT, ...]:
    result: list[SegmentT] = []
    found = False
    for segment in segments:
        if segment.id != segment_id:
            result.append(segment)
            continue
        if offset <= 0 or offset >= len(segment.source_text):
            raise ValueError("split offset must be inside the segment")
        left = segment.source_text[:offset].strip()
        right = segment.source_text[offset:].strip()
        if not left or not right:
            raise ValueError("split must produce two non-empty segments")
        result.append(replace(segment, source_text=left))
        result.append(
            replace(
                segment,
                id=new_id or stable_id(),
                source_text=right,
                reference_text=None,
                unknown_fields={},
            )
        )
        found = True
    if not found:
        raise KeyError(segment_id)
    return _validate_edited(result, limits)


def merge_segments(
    segments: Iterable[SegmentT], first_id: str, second_id: str, *, separator: str = "\n\n",
    limits: SegmentationLimits | None = None,
) -> tuple[SegmentT, ...]:
    current = tuple(segments)
    first_index = next((i for i, item in enumerate(current) if item.id == first_id), -1)
    second_index = next((i for i, item in enumerate(current) if item.id == second_id), -1)
    if first_index < 0 or second_index < 0:
        raise KeyError(first_id if first_index < 0 else second_id)
    if second_index != first_index + 1:
        raise ValueError("only adjacent segments can be merged")
    first, second = current[first_index], current[second_index]
    reference_parts = [value for value in (first.reference_text, second.reference_text) if value]
    merged = replace(
        first,
        source_text=f"{first.source_text}{separator}{second.source_text}",
        reference_text=separator.join(reference_parts) or None,
    )
    return _validate_edited((*current[:first_index], merged, *current[second_index + 1 :]), limits)
