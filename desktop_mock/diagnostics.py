"""Health checks for standalone desktop providers.

The functions here intentionally return plain dictionaries so the desktop
launcher can print human-readable output while tests can assert exact states.
No check should leak API tokens, raw Authorization headers, or provider error
payloads.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Mapping

from ankiconnect_card_saver import (
    ARTICLE_FIELDS,
    ARTICLE_NOTE_TYPE,
    AnkiConnectArticleCardSaver,
    AnkiConnectCardSaverError,
)
from ankiconnect_provider import ANKICONNECT_VERSION, DEFAULT_ANKICONNECT_URL
from momo_provider import MockMoMoDeckProvider
from real_momo_provider import RealMoMoDeckProvider


DiagnosticResult = dict[str, Any]
Opener = Callable[..., Any]


def run_diagnostics(
    provider: str,
    *,
    environ: Mapping[str, str] | None = None,
    opener: Opener | None = None,
    provider_factory: Callable[[str], Any] | None = None,
) -> DiagnosticResult:
    """Run provider-specific diagnostics and return a structured result."""
    if environ is None:
        environ = os.environ

    try:
        if provider == "mock":
            result = _check_mock(provider_factory=provider_factory)
        elif provider == "ankiconnect":
            base_url = environ.get("DAIRR_ANKICONNECT_URL", DEFAULT_ANKICONNECT_URL)
            result = _check_ankiconnect(base_url, opener=opener)
        elif provider == "real_momo":
            token = environ.get("MOMO_TOKEN") or environ.get("Maimemo_key")
            result = _check_real_momo(token, provider_factory=provider_factory)
        else:
            result = {
                "provider": provider,
                "checks": [_check("provider", False, "The requested diagnostic provider is unknown.")],
            }
    except Exception as exc:
        # Provider construction is third-party code too. Apply the same fixed
        # privacy boundary as individual checks rather than allowing arbitrary
        # exception text to reach a CLI, log, or screenshot.
        result = {
            "provider": provider,
            "checks": [_check("provider initialization", False, _safe_error_message(exc))],
        }

    result["ok"] = all(item.get("ok") for item in result.get("checks", []))
    return result


def run_write_diagnostics(
    provider: str = "ankiconnect",
    *,
    environ: Mapping[str, str] | None = None,
    opener: Opener | None = None,
) -> DiagnosticResult:
    """Write one DAIRR smoke-test article card through AnkiConnect."""
    if environ is None:
        environ = os.environ

    checks: list[dict[str, Any]] = []
    result: DiagnosticResult = {
        "provider": provider,
        "mode": "write",
        "checks": checks,
    }

    if provider != "ankiconnect":
        checks.append(_check("provider", False, "--check-write requires provider ankiconnect."))
        result["ok"] = False
        return result

    base_url = environ.get("DAIRR_ANKICONNECT_URL", DEFAULT_ANKICONNECT_URL)
    recording_opener = _RecordingOpener(opener or urllib.request.urlopen)
    client = _AnkiConnectDiagnosticClient(base_url=base_url, opener=recording_opener)

    try:
        version = client.invoke("version")
    except Exception as exc:
        checks.append(_check("AnkiConnect reachable", False, _safe_error_message(exc)))
        checks.append(_check("article note created", False, "Skipped because AnkiConnect is not reachable."))
        checks.append(_check("returned noteId", False, "Unavailable."))
        checks.append(_check("suspend attempted", False, "Skipped."))
        result["ok"] = False
        return result

    checks.append(_check("AnkiConnect reachable", True, f"AnkiConnect version: {version}"))

    saver = AnkiConnectArticleCardSaver(base_url=base_url, opener=recording_opener)
    try:
        save_result = saver.save_article_card(
            "DAIRR Smoke Test",
            [{"term": "dairr-smoke-term"}],
            "DAIRR AnkiConnect write smoke test article.",
            Path("/tmp/dairr-smoke-test.md"),
            Path("/tmp/dairr-smoke-test.html"),
        )
    except Exception as exc:
        checks.append(_check("article note created", False, _safe_error_message(exc)))
        checks.append(_check("returned noteId", False, "Unavailable."))
        _append_suspend_checks(checks, recording_opener.records)
        result["ok"] = False
        return result

    note_id = save_result.get("noteId") if isinstance(save_result, dict) else None
    checks.append(_check("article note created", True, "Smoke test article note was created."))
    checks.append(_check("returned noteId", isinstance(note_id, int), str(note_id) if note_id else "Unavailable."))
    _append_suspend_checks(checks, recording_opener.records)

    result["noteId"] = note_id
    result["ok"] = all(item.get("ok") for item in checks)
    return result


def format_diagnostics(result: DiagnosticResult) -> str:
    """Return safe, human-readable diagnostic output."""
    status = "OK" if result.get("ok") else "FAILED"
    provider = str(result.get("provider") or "")
    label = "DAIRR desktop write check" if result.get("mode") == "write" else "DAIRR desktop check"
    lines = [f"{label}: {status}", f"Provider: {provider}"]
    for item in result.get("checks", []):
        mark = "OK" if item.get("ok") else "FAIL"
        name = str(item.get("name") or "check")
        message = str(item.get("message") or "")
        lines.append(f"- [{mark}] {name}: {message}")
    return "\n".join(lines)


def _check_mock(
    *,
    provider_factory: Callable[[str], Any] | None = None,
) -> DiagnosticResult:
    checks: list[dict[str, Any]] = []
    provider = _make_provider("mock", provider_factory, MockMoMoDeckProvider)
    decks = _call_check(checks, "provider decks", lambda: provider.get_today_decks())
    if isinstance(decks, list) and decks:
        checks.append(_check("deck list", True, f"Found {len(decks)} deck(s)."))
        deck_id = str(decks[0].get("id") or "")
        cards = _call_check(
            checks,
            "provider cards",
            lambda: provider.get_deck_cards(deck_id),
        )
        card_count = len(cards.get("cards", [])) if isinstance(cards, dict) else 0
        checks.append(_check("card list", card_count > 0, f"Found {card_count} card(s)."))
    else:
        checks.append(_check("deck list", False, "Provider returned no decks."))
    return {"provider": "mock", "checks": checks}


def _check_real_momo(
    token: str | None,
    *,
    provider_factory: Callable[[str], Any] | None = None,
) -> DiagnosticResult:
    checks: list[dict[str, Any]] = []
    if token:
        checks.append(_check("token", True, "MoMo token is present."))
    else:
        checks.append(_check("token", False, "MOMO_TOKEN or Maimemo_key is missing."))
        return {"provider": "real_momo", "checks": checks}

    def init_provider() -> Any:
        if provider_factory is not None:
            return provider_factory("real_momo")
        return RealMoMoDeckProvider(token=token)

    try:
        init_provider()
    except Exception as exc:
        checks.append(_check("provider init", False, _safe_error_message(exc)))
    else:
        checks.append(_check("provider init", True, "Real MoMo provider initialized."))
    return {"provider": "real_momo", "checks": checks}


def _check_ankiconnect(base_url: str, *, opener: Opener | None = None) -> DiagnosticResult:
    client = _AnkiConnectDiagnosticClient(base_url=base_url, opener=opener)
    checks: list[dict[str, Any]] = []

    version = _call_check(checks, "endpoint reachable", lambda: client.invoke("version"))
    if version is not None:
        checks.append(_check("response envelope", True, f"AnkiConnect version: {version}"))

    model_names = _call_check(checks, "modelNames", lambda: client.invoke("modelNames"))
    if isinstance(model_names, list):
        checks.append(_check("modelNames result", True, f"Found {len(model_names)} note type(s)."))
    elif model_names is not None:
        checks.append(_check("modelNames result", False, "modelNames did not return a list."))

    rated_cards = _call_check(
        checks,
        "findCards rated:1",
        lambda: client.invoke("findCards", {"query": "rated:1"}),
    )
    if isinstance(rated_cards, list):
        checks.append(_check("rated cards", True, f"Found {len(rated_cards)} rated card(s) today."))
    elif rated_cards is not None:
        checks.append(_check("rated cards", False, "findCards rated:1 did not return a list."))

    if isinstance(rated_cards, list) and rated_cards:
        sample_ids = rated_cards[:20]
        cards_info = _call_check(
            checks,
            "cardsInfo",
            lambda: client.invoke("cardsInfo", {"cards": sample_ids}),
        )
        if isinstance(cards_info, list):
            checks.append(_check("cardsInfo result", True, f"Read {len(cards_info)} card info row(s)."))
        elif cards_info is not None:
            checks.append(_check("cardsInfo result", False, "cardsInfo did not return a list."))
    elif isinstance(rated_cards, list):
        checks.append(_check("cardsInfo", True, "Skipped because rated:1 returned no cards."))

    if not isinstance(model_names, list):
        checks.append(
            _check(
                "article note type",
                False,
                "Skipped because modelNames was unavailable.",
            )
        )
    elif ARTICLE_NOTE_TYPE not in [str(name) for name in model_names]:
        checks.append(
            _check(
                "article note type",
                True,
                f"{ARTICLE_NOTE_TYPE} is missing; will create on first save.",
            )
        )
    else:
        checks.append(_check("article note type", True, f"{ARTICLE_NOTE_TYPE} exists."))
        fields = _call_check(
            checks,
            "article fields",
            lambda: client.invoke("modelFieldNames", {"modelName": ARTICLE_NOTE_TYPE}),
        )
        if isinstance(fields, list):
            missing = [field for field in ARTICLE_FIELDS if field not in fields]
            if missing:
                checks.append(
                    _check(
                        "article fields compatible",
                        False,
                        "Article note type is missing field(s): " + ", ".join(missing),
                    )
                )
            else:
                checks.append(
                    _check(
                        "article fields compatible",
                        True,
                        "Article note type contains all DAIRR article fields.",
                    )
                )
        elif fields is not None:
            checks.append(
                _check("article fields compatible", False, "modelFieldNames did not return a list.")
            )

    return {"provider": "ankiconnect", "checks": checks}


class _AnkiConnectDiagnosticClient:
    def __init__(
        self,
        *,
        base_url: str,
        timeout: float = 10.0,
        opener: Opener | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._opener = opener or urllib.request.urlopen

    def invoke(self, action: str, params: dict[str, Any] | None = None) -> Any:
        payload = {
            "action": action,
            "version": ANKICONNECT_VERSION,
            "params": params or {},
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self._base_url,
            data=data,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "dairr-diagnostics/0.1",
            },
            method="POST",
        )
        try:
            with self._opener(req, timeout=self._timeout) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as exc:
            raise _DiagnosticError(f"HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise _DiagnosticError("Could not reach AnkiConnect.") from exc

        try:
            body = json.loads(raw.decode("utf-8", errors="replace") if raw else "{}")
        except json.JSONDecodeError as exc:
            raise _DiagnosticError("Invalid JSON from AnkiConnect.") from exc

        if not isinstance(body, dict):
            raise _DiagnosticError("Invalid AnkiConnect response envelope.")
        if "error" not in body or "result" not in body:
            raise _DiagnosticError("AnkiConnect response envelope is missing result/error.")
        if body.get("error"):
            raise _DiagnosticError("AnkiConnect returned an error.")
        return body.get("result")


class _DiagnosticError(RuntimeError):
    """Safe diagnostic error for user-facing output."""


class _RecordingOpener:
    def __init__(self, opener: Opener) -> None:
        self._opener = opener
        self.records: list[dict[str, Any]] = []

    def __call__(self, req: Any, timeout: float = 0) -> Any:
        action = _request_action(req)
        record = {"action": action, "body": None, "exception": None}
        self.records.append(record)
        try:
            response = self._opener(req, timeout=timeout)
        except Exception as exc:
            record["exception"] = type(exc).__name__
            raise
        return _RecordingResponse(response, record)


class _RecordingResponse:
    def __init__(self, response: Any, record: dict[str, Any]) -> None:
        self._response = response
        self._active_response = response
        self._record = record

    def __enter__(self) -> "_RecordingResponse":
        if hasattr(self._response, "__enter__"):
            self._active_response = self._response.__enter__()
        return self

    def __exit__(self, *args: Any) -> Any:
        if hasattr(self._response, "__exit__"):
            return self._response.__exit__(*args)
        return None

    def read(self) -> bytes:
        raw = self._active_response.read()
        try:
            text = raw.decode("utf-8", errors="replace") if raw else "{}"
            self._record["body"] = json.loads(text)
        except Exception:
            self._record["body"] = None
        return raw


def _make_provider(
    provider: str,
    provider_factory: Callable[[str], Any] | None,
    default_factory: Callable[[], Any],
) -> Any:
    if provider_factory is not None:
        return provider_factory(provider)
    return default_factory()


def _call_check(
    checks: list[dict[str, Any]],
    name: str,
    callback: Callable[[], Any],
) -> Any:
    try:
        result = callback()
    except Exception as exc:
        checks.append(_check(name, False, _safe_error_message(exc)))
        return None
    checks.append(_check(name, True, "Callable."))
    return result


def _check(name: str, ok: bool, message: str) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "message": message}


def _safe_error_message(exc: BaseException) -> str:
    if isinstance(exc, _DiagnosticError):
        return str(exc) or "Diagnostic request failed."
    if isinstance(exc, AnkiConnectCardSaverError):
        return exc.public_message
    if isinstance(exc, ValueError):
        # ValueError text can be supplied by third-party providers and may
        # contain a URL, credential, request body, or private card content.
        return "Diagnostic input or provider configuration is invalid."
    return "Diagnostic request failed."


def _request_action(req: Any) -> str:
    data = getattr(req, "data", None)
    if not data:
        return ""
    try:
        payload = json.loads(data.decode("utf-8"))
    except Exception:
        return ""
    return str(payload.get("action") or "")


def _append_suspend_checks(checks: list[dict[str, Any]], records: list[dict[str, Any]]) -> None:
    suspend_records = [record for record in records if record.get("action") == "suspend"]
    if not suspend_records:
        checks.append(_check("suspend attempted", False, "No suspend request was made."))
        checks.append(_check("suspend succeeded", False, "Could not confirm suspend succeeded."))
        return

    checks.append(_check("suspend attempted", True, "suspend was called."))
    succeeded = any(_record_succeeded(record) for record in suspend_records)
    message = (
        "AnkiConnect accepted the suspend request."
        if succeeded
        else "Could not confirm suspend succeeded."
    )
    checks.append(_check("suspend succeeded", succeeded, message))


def _record_succeeded(record: dict[str, Any]) -> bool:
    body = record.get("body")
    return (
        record.get("exception") is None
        and isinstance(body, dict)
        and body.get("error") in (None, "")
        and "result" in body
    )
