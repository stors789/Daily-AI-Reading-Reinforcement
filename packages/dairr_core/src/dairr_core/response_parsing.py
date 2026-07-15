"""Tolerant parsing of untrusted plain-text and structured model responses."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any

from .prompt_templates import ResponseMode


class ResponseParseError(ValueError):
    """A privacy-safe parsing failure that never embeds response content."""

    def __init__(self, code: str, message: str, *, possibly_truncated: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.possibly_truncated = possibly_truncated


@dataclass(frozen=True, slots=True)
class ParsedModelResponse:
    mode: ResponseMode
    text: str = ""
    data: Any = None
    warnings: tuple[str, ...] = ()
    recovered_from_wrapper: bool = False
    possibly_truncated: bool = False


def parse_model_response(
    raw: Any,
    mode: ResponseMode,
    *,
    finish_reason: str | None = None,
) -> ParsedModelResponse:
    if not isinstance(raw, str) or not raw.strip():
        raise ResponseParseError("empty_response", "The model returned an empty response.")
    truncated = str(finish_reason or "").lower() in {"length", "max_tokens", "token_limit"}
    if mode is ResponseMode.PLAIN_TEXT:
        return ParsedModelResponse(mode, text=raw.strip(), possibly_truncated=truncated)
    return _parse_structured(raw, truncated)


def _parse_structured(raw: str, truncated: bool) -> ParsedModelResponse:
    candidate, fenced = _strip_code_fence(raw.strip())
    warnings: list[str] = []
    if fenced:
        warnings.append("Removed a provider-added code fence.")
    parsed, duplicates, recovered = _decode_json_object(candidate)
    if parsed is None:
        likely_truncated = truncated or _looks_truncated(candidate)
        raise ResponseParseError(
            "truncated_json" if likely_truncated else "invalid_json",
            "The structured model response was truncated. Retry with a larger output limit."
            if likely_truncated
            else "The model did not return a valid JSON object.",
            possibly_truncated=likely_truncated,
        )
    if duplicates:
        warnings.append("Duplicate JSON fields were present; the final value was used.")
    if recovered:
        warnings.append("Recovered JSON from provider-added wrapper text.")
    data, unwrapped = _unwrap_known_envelope(parsed)
    if unwrapped:
        recovered = True
        warnings.append("Removed a provider-added response envelope.")
    if not isinstance(data, dict):
        raise ResponseParseError("invalid_root", "The structured response must contain one JSON object.")
    return ParsedModelResponse(
        ResponseMode.STRUCTURED,
        data=data,
        warnings=tuple(warnings),
        recovered_from_wrapper=recovered,
        possibly_truncated=truncated,
    )


def _strip_code_fence(text: str) -> tuple[str, bool]:
    match = re.fullmatch(r"\s*```(?:json|JSON)?\s*\n?(.*?)\n?```\s*", text, flags=re.DOTALL)
    return (match.group(1).strip(), True) if match else (text, False)


def _decode_json_object(text: str) -> tuple[Any | None, tuple[str, ...], bool]:
    duplicate_keys: list[str] = []

    def pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                duplicate_keys.append(key)
            result[key] = value
        return result

    decoder = json.JSONDecoder(object_pairs_hook=pairs_hook)
    try:
        value, end = decoder.raw_decode(text)
        if text[end:].strip():
            raise json.JSONDecodeError("trailing content", text, end)
        return value, tuple(sorted(set(duplicate_keys))), False
    except json.JSONDecodeError:
        pass
    # Providers sometimes prepend prose or append a signature. Scan only for
    # an object and require all remaining non-whitespace text to be harmless.
    for index, char in enumerate(text):
        if char != "{":
            continue
        duplicate_keys.clear()
        try:
            value, end = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value, tuple(sorted(set(duplicate_keys))), bool(index or text[index + end :].strip())
    return None, (), False


def _unwrap_known_envelope(value: dict[str, Any]) -> tuple[Any, bool]:
    for key in ("result", "response", "review", "data"):
        if len(value) == 1 and isinstance(value.get(key), dict):
            return value[key], True
    return value, False


def _looks_truncated(text: str) -> bool:
    in_string = False
    escaped = False
    depth = 0
    for char in text:
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char in "[{":
            depth += 1
        elif char in "]}":
            depth -= 1
    return in_string or depth > 0
