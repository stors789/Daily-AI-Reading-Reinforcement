#!/usr/bin/env python3
"""Inspect the standalone desktop debugPrompt bridge action."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


SUMMARY_FIELDS = (
    "selectedPromptPresetId",
    "requestedPresetId",
    "articleLanguage",
    "readerNativeLanguage",
    "cardCount",
    "selectedFields",
    "promptContainsArticleLanguage",
    "promptPreview",
)


def build_request_body(args: argparse.Namespace) -> dict[str, Any]:
    payload: dict[str, Any] = {"deckId": args.deck_id}
    if args.preset_id:
        payload["presetId"] = args.preset_id
    if args.card_id:
        payload["cardIds"] = list(args.card_id)
    return {"action": "debugPrompt", "payload": payload}


def call_debug_prompt(
    url: str,
    body: dict[str, Any],
    opener: Any | None = None,
) -> dict[str, Any]:
    bridge_url = urllib.parse.urljoin(url.rstrip("/") + "/", "api/bridge")
    request = urllib.request.Request(
        bridge_url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    active_opener = opener or urllib.request.build_opener()
    with active_opener.open(request, timeout=10) as response:
        raw = response.read()
    try:
        result = json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise ValueError("Response was not valid UTF-8.") from exc
    except json.JSONDecodeError as exc:
        raise ValueError("Response was not valid JSON.") from exc
    if not isinstance(result, dict):
        raise ValueError("Response JSON was not an object.")
    return result


def print_summary(result: dict[str, Any], stream: Any | None = None) -> None:
    if stream is None:
        stream = sys.stdout
    payload = result.get("payload")
    if not isinstance(payload, dict):
        payload = {}
    for field in SUMMARY_FIELDS:
        value = payload.get(field, "")
        if isinstance(value, (dict, list)):
            value_text = json.dumps(value, ensure_ascii=False)
        else:
            value_text = str(value)
        print(f"{field}: {value_text}", file=stream)


def print_result(
    result: dict[str, Any],
    as_json: bool,
    stream: Any | None = None,
) -> int:
    if stream is None:
        stream = sys.stdout
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2), file=stream)
        return 0

    if result.get("event") == "error":
        payload = result.get("payload")
        message = ""
        if isinstance(payload, dict):
            message = str(payload.get("message") or "")
        print(f"Bridge error: {message or 'Unknown error.'}", file=sys.stderr)
        return 1

    print_summary(result, stream=stream)
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Call the standalone desktop debugPrompt bridge action."
    )
    parser.add_argument("--url", default="http://127.0.0.1:8755")
    parser.add_argument("--deck-id", required=True)
    parser.add_argument("--preset-id", default="")
    parser.add_argument("--card-id", action="append", default=[])
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, opener: Any | None = None) -> int:
    args = parse_args(argv)
    body = build_request_body(args)
    try:
        result = call_debug_prompt(args.url, body, opener=opener)
    except urllib.error.HTTPError as exc:
        print(f"HTTP error from standalone server: {exc.code} {exc.reason}", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(
            "Could not reach standalone server. Start it with "
            "`python3 desktop_app.py --provider ankiconnect --no-browser` "
            f"and try again. Details: {exc.reason}",
            file=sys.stderr,
        )
        return 1
    except ValueError as exc:
        print(f"Invalid JSON response from standalone server: {exc}", file=sys.stderr)
        return 1
    return print_result(result, args.as_json)


if __name__ == "__main__":
    raise SystemExit(main())
