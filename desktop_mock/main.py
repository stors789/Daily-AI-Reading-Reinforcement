# Desktop mock server for Daily AI Reading Reinforcement.
#
# Serves the SAME shared web UI (addon/daily_ai_reading_reinforcement/web/*)
# that the Anki addon uses, but in a plain Python http.server with no Anki /
# aqt / momo / LLM dependencies. A mock window.__DAIRR_BRIDGE__ is injected so
# app.js's send() talks to /api/bridge, which returns mock responses that
# match the real addon's event payloads.
#
# Run:  python3 desktop_mock/main.py
# Open: http://127.0.0.1:8755

from __future__ import annotations

import json
import os
import sys
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping

from mock_data import (
    build_article_list_payload,
    build_article_payload,
    build_deck_cards_payload,
    build_loaded_article_payload,
    build_state_payload,
)
from momo_provider import MockMoMoDeckProvider
from real_momo_provider import RealMoMoDeckProvider

REPO_ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = REPO_ROOT / "addon" / "daily_ai_reading_reinforcement" / "web"
HOST = "127.0.0.1"
# 8765 is AnkiConnect's default port; pick a distinct one to avoid clashes
# when Anki is running alongside the mock.
PORT = 8755


def build_deck_provider(environ: Mapping[str, str] | None = None) -> Any:
    if environ is None:
        environ = os.environ
       

    provider_type = environ.get("DAIRR_DESKTOP_PROVIDER", "mock")
    if provider_type == "real_momo":
        token = environ.get("MOMO_TOKEN") or environ.get("Maimemo_key")
        if not token:
            raise ValueError("MOMO_TOKEN is missing. Cannot start real_momo provider.")
        print("Using RealMoMoDeckProvider (MOMO_TOKEN present)")
        return RealMoMoDeckProvider(token=token)
    elif provider_type == "mock":
        print("Using MockMoMoDeckProvider")
        return MockMoMoDeckProvider()
    else:
        raise ValueError(f"Unknown DAIRR_DESKTOP_PROVIDER: {provider_type}")


# Single provider instance used by handle_action() for load / selectDeck.
try:
    DECK_PROVIDER = build_deck_provider()
except Exception as e:
    print(f"Failed to initialize deck provider: {e}")
    sys.exit(1)


# Actions the mock understands. Anything else returns an error event so the
# shared UI's error handling path is exercised without crashing the server.
SUPPORTED_ACTIONS = {
    "load",
    "selectDeck",
    "generate",
    "listArticles",
    "loadArticle",
}


def safe_exception_summary(exc: BaseException | None) -> str:
    if exc is None:
        return "-"
    # For urllib.error.HTTPError, include only status code and class name.
    code = getattr(exc, "code", None)
    if code is not None:
        return f"{type(exc).__name__}(code={code})"
    reason = getattr(exc, "reason", None)
    if reason is not None:
        return f"{type(exc).__name__}"
    return type(exc).__name__


def handle_action(action: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Dispatch one bridge action and return an {event, payload} envelope.

    This is the unit-testable core: it does no I/O and touches no network.
    The HTTP handler below is a thin wrapper around it.
    """
    if action == "load":
        last_selected = str((payload or {}).get("lastSelectedDeckId") or "")
        try:
            decks = DECK_PROVIDER.get_today_decks()
            return {"event": "state", "payload": build_state_payload(last_selected, decks=decks)}
        except Exception as exc:
            err_type = type(exc).__name__
            sys.stderr.write(f"[mock] Provider error on load: {err_type}\n")
            return {"event": "error", "payload": {"message": "Failed to load decks from provider."}}

    if action == "selectDeck":
        deck_id = str((payload or {}).get("deckId") or "")
        try:
            cards_data = DECK_PROVIDER.get_deck_cards(deck_id)
            return {"event": "deckCards", "payload": build_deck_cards_payload(deck_id, cards_data=cards_data)}
        except Exception as exc:
            err_type = type(exc).__name__
            stage = getattr(exc, "stage", None)
            cause_summary = safe_exception_summary(getattr(exc, "__cause__", None))
            if stage:
                msg = f"Failed to load deck cards from provider. Stage: {stage}"
                sys.stderr.write(f"[mock] Provider error on selectDeck: {err_type} stage={stage} cause={cause_summary}\n")
            else:
                msg = "Failed to load deck cards from provider."
                sys.stderr.write(f"[mock] Provider error on selectDeck: {err_type} cause={cause_summary}\n")
            return {"event": "error", "payload": {"message": msg}}

    if action == "generate":
        deck_id = str((payload or {}).get("deckId") or "")
        return {"event": "article", "payload": build_article_payload(deck_id)}

    if action == "listArticles":
        return {"event": "articleList", "payload": build_article_list_payload()}

    if action == "loadArticle":
        path = str((payload or {}).get("path") or "")
        return {"event": "articleLoaded", "payload": build_loaded_article_payload(path)}

    return {"event": "error", "payload": {"message": f"Unknown command: {action}"}}


@lru_cache(maxsize=1)
def _build_index_page() -> str:
    """Inline css + index.html body + mock bridge + app.js, mirroring _load_page."""
    body = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    css = (WEB_DIR / "style.css").read_text(encoding="utf-8")
    js = (WEB_DIR / "app.js").read_text(encoding="utf-8")
    guard = (
        '<script>\n'
        'window.addEventListener("error", function (event) {\n'
        '  document.body.innerHTML = \'<main class="app-shell"><section class="panel" style="padding:24px;"><h1>AI Reading Reinforcement</h1><p>Page script error: \' + String(event.message || "unknown") + \'</p></section></main>\';\n'
        '});\n'
        '</script>\n'
    )
    # The mock bridge replaces the Anki pycmd path. It posts to /api/bridge and
    # feeds the response straight into the shared app.js receive handler
    # (window.DAIRR.receive), which expects { event, payload }.
    bridge = (
        '<script>\n'
        'window.__DAIRR_BRIDGE__ = {\n'
        '  send(action, payload) {\n'
        '    fetch("/api/bridge", {\n'
        '      method: "POST",\n'
        '      headers: {"Content-Type": "application/json"},\n'
        '      body: JSON.stringify({action: action, payload: payload})\n'
        '    })\n'
        '      .then(function (r) { return r.json(); })\n'
        '      .then(function (data) {\n'
        '        if (window.DAIRR && typeof window.DAIRR.receive === "function") {\n'
        '          window.DAIRR.receive(data);\n'
        '        }\n'
        '      })\n'
        '      .catch(function (err) { console.error("Mock bridge error", err); });\n'
        '  }\n'
        '};\n'
        '</script>\n'
    )
    return f"<style>{css}</style>\n{body}\n{guard}{bridge}<script>{js}</script>"


class MockHandler(BaseHTTPRequestHandler):
    server_version = "DAIRRMock/1.0"

    def _send_json(self, status: int, obj: dict[str, Any]) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/" or self.path == "/index.html":
            self._send_html(_build_index_page())
            return
        self.send_error(404, "Not found")

    def do_POST(self) -> None:
        if self.path != "/api/bridge":
            self.send_error(404, "Not found")
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            message = json.loads(raw.decode("utf-8") or "{}")
        except Exception as exc:
            self._send_json(400, {"event": "error", "payload": {"message": f"Bad request: {exc}"}})
            return

        action = str(message.get("action") or "")
        payload = message.get("payload") or {}
        if not isinstance(payload, dict):
            payload = {}
        try:
            self._send_json(200, handle_action(action, payload))
        except Exception as exc:
            self._send_json(200, {"event": "error", "payload": {"message": str(exc)}})

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("[mock] " + (fmt % args) + "\n")


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), MockHandler)
    print(f"DAIRR desktop mock running at http://{HOST}:{PORT}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping.")
        server.shutdown()


if __name__ == "__main__":
    main()
