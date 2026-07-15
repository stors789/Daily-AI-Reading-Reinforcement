#!/usr/bin/env python3
"""Inspect the standalone desktop debugPrompt bridge action."""

from __future__ import annotations

import argparse
import json
import re
import secrets
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
BRIDGE_TOKEN_HEADER = "X-DAIRR-Bridge-Token"
TOKEN_PATTERN = re.compile(r"window\.__DAIRR_BRIDGE_TOKEN__\s*=\s*(\"(?:[^\"\\]|\\.)*\")\s*;")


def build_request_body(args: argparse.Namespace) -> dict[str, Any]:
    payload: dict[str, Any] = {"deckId": args.deck_id}
    if args.preset_id:
        payload["presetId"] = args.preset_id
    if args.card_id:
        payload["cardIds"] = list(args.card_id)
    return {
        "version": 2,
        "requestId": f"debug-{secrets.token_hex(12)}",
        "action": "debugPrompt",
        "payload": payload,
    }


def _local_base_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("The standalone debug URL must be an HTTP loopback address.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("The standalone debug URL contains unsupported components.")
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))


def discover_bridge_token(url: str, opener: Any) -> str:
    """Read the token from the same-origin bootstrap without printing it."""
    base_url = _local_base_url(url)
    index_url = urllib.parse.urljoin(base_url.rstrip("/") + "/", "index.html")
    request = urllib.request.Request(index_url, headers={"Accept": "text/html"}, method="GET")
    with opener.open(request, timeout=10) as response:
        raw = response.read()
    try:
        page = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Standalone bootstrap was not valid UTF-8.") from exc
    match = TOKEN_PATTERN.search(page)
    if match is None:
        raise ValueError("Standalone bootstrap did not provide a bridge token.")
    try:
        token = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise ValueError("Standalone bootstrap contained an invalid bridge token.") from exc
    if not isinstance(token, str) or len(token) < 20:
        raise ValueError("Standalone bootstrap contained an invalid bridge token.")
    return token


def call_debug_prompt(
    url: str,
    body: dict[str, Any],
    opener: Any | None = None,
) -> dict[str, Any]:
    active_opener = opener or urllib.request.build_opener()
    base_url = _local_base_url(url)
    bridge_token = discover_bridge_token(base_url, active_opener)
    bridge_url = urllib.parse.urljoin(base_url.rstrip("/") + "/", "api/bridge")
    request = urllib.request.Request(
        bridge_url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", BRIDGE_TOKEN_HEADER: bridge_token},
        method="POST",
    )
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
    failed = result.get("event") in {"error", "operationFailed", "operationCancelled"}
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2), file=stream)
        return 1 if failed else 0

    if failed:
        payload = result.get("payload")
        message = ""
        if isinstance(payload, dict):
            error = payload.get("error") if isinstance(payload.get("error"), dict) else {}
            message = str(error.get("message") or payload.get("message") or "")
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
        print(f"HTTP error from standalone server: {exc.code}", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(
            "Could not reach standalone server. Start it with "
            "`python3 desktop_app.py --provider ankiconnect --no-browser` "
            "and try again.",
            file=sys.stderr,
        )
        return 1
    except ValueError as exc:
        print(f"Invalid JSON response from standalone server: {exc}", file=sys.stderr)
        return 1
    return print_result(result, args.as_json)


if __name__ == "__main__":
    raise SystemExit(main())
