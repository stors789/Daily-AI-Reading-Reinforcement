from __future__ import annotations

import importlib
import json
import sqlite3
import sys
import tempfile
import types
import unittest
from concurrent.futures import Future
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "packages" / "dairr_core" / "src"
ADDON = ROOT / "addon"
for path in (CORE, ADDON):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


class _Signal:
    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)


class _Dialog:
    def __init__(self, *_args):
        pass

    def setWindowTitle(self, _title):
        pass

    def resize(self, *_size):
        pass

    def setLayout(self, _layout):
        pass

    def done(self, _result):
        pass

    def closeEvent(self, _event):
        pass


class _Web:
    def __init__(self):
        self.evaluated = []

    def set_bridge_command(self, callback, context):
        self.bridge = callback
        self.context = context

    def stdHtml(self, _page, context=None):
        self.html_context = context

    def eval(self, script):
        self.evaluated.append(script)


class _Taskman:
    def __init__(self):
        self.jobs = []

    def run_in_background(self, task, done):
        self.jobs.append((task, done))

    def finish(self, index=0):
        task, done = self.jobs[index]
        future = Future()
        try:
            future.set_result(task())
        except BaseException as exc:
            future.set_exception(exc)
        done(future)


class _AddonManager:
    def __init__(self):
        self.config = {}

    def getConfig(self, _package):
        return dict(self.config)

    def writeConfig(self, _package, config):
        self.config = dict(config)

    def setWebExports(self, *_args):
        pass


def _install_fake_aqt():
    taskman = _Taskman()
    addon_manager = _AddonManager()
    mw = types.SimpleNamespace(
        col=None,
        taskman=taskman,
        addonManager=addon_manager,
        form=types.SimpleNamespace(menuTools=types.SimpleNamespace(addAction=lambda _action: None)),
    )
    hooks = types.SimpleNamespace(
        deck_browser_will_render_content=[],
        webview_did_receive_js_message=[],
        profile_will_close=[],
        collection_will_close=[],
    )
    aqt = types.ModuleType("aqt")
    aqt.mw = mw
    aqt.gui_hooks = hooks
    deckbrowser = types.ModuleType("aqt.deckbrowser")
    deckbrowser.DeckBrowser = type("DeckBrowser", (), {"_linkHandler": lambda *_args: None})
    qt = types.ModuleType("aqt.qt")
    qt.QAction = lambda *_args: types.SimpleNamespace(triggered=_Signal())
    qt.QDialog = _Dialog
    qt.QTimer = types.SimpleNamespace(singleShot=lambda _delay, callback: callback())
    qt.QVBoxLayout = type(
        "QVBoxLayout",
        (),
        {"setContentsMargins": lambda *_args: None, "addWidget": lambda *_args: None},
    )
    utils = types.ModuleType("aqt.utils")
    utils.showWarning = lambda _message: None
    webview = types.ModuleType("aqt.webview")
    webview.AnkiWebView = _Web
    aqt.deckbrowser = deckbrowser
    sys.modules.update({
        "aqt": aqt,
        "aqt.deckbrowser": deckbrowser,
        "aqt.qt": qt,
        "aqt.utils": utils,
        "aqt.webview": webview,
    })
    return mw, hooks


def _last_envelope(dialog):
    script = dialog.web.evaluated[-1]
    return json.loads(script.removeprefix("window.DAIRR.receive(").removesuffix(");"))


class AddonWrapperIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mw, cls.hooks = _install_fake_aqt()
        cls.module = importlib.import_module("daily_ai_reading_reinforcement")

    def setUp(self):
        self.mw.taskman.jobs.clear()
        self.mw.addonManager.config = {}
        self.dialog = self.module.ReadingReinforcementDialog()

    def tearDown(self):
        self.dialog._dispose_operations()
        self.mw.col = None

    def test_v2_capability_and_pasted_practice_actions(self):
        self.dialog._on_bridge_command(json.dumps({
            "version": 2,
            "requestId": "cap-1",
            "action": "getCapabilities",
            "payload": {},
        }))
        response = _last_envelope(self.dialog)
        self.assertEqual(response["version"], 2)
        self.assertEqual(response["requestId"], "cap-1")
        self.assertEqual(response["payload"]["capabilities"]["anki_connection"]["reason"], "profile_closed")
        self.assertEqual(response["payload"]["capabilities"]["pasted_text_practice"]["status"], "available")

        self.dialog._on_bridge_command(json.dumps({
            "version": 2,
            "requestId": "practice-1",
            "action": "createPastedPractice",
            "payload": {
                "sourceText": "private draft",
                "sourceLanguage": "en",
                "targetLanguage": "ja",
            },
        }))
        response = _last_envelope(self.dialog)
        self.assertEqual(response["event"], "practiceSessionCreated")
        self.assertEqual(response["payload"]["session"]["sourceText"], "private draft")

    def test_profile_closed_failure_is_redacted(self):
        self.dialog._on_bridge_command(json.dumps({
            "version": 2,
            "requestId": "study-1",
            "action": "loadStudySignals",
            "payload": {},
        }))
        response = _last_envelope(self.dialog)
        self.assertEqual(response["event"], "operationFailed")
        self.assertEqual(response["payload"]["error"]["code"], "profile_closed")

    def test_dialog_close_discards_late_background_callback(self):
        self.module.fetch_openai_compatible_models = lambda *_args: ["model-a"]
        self.dialog._on_bridge_command(json.dumps({
            "version": 2,
            "requestId": "models-1",
            "action": "fetchModels",
            "payload": {"settings": {"apiKey": "secret", "baseUrl": "https://example.invalid"}},
        }))
        accepted_count = len(self.dialog.web.evaluated)
        self.dialog.done(0)
        self.mw.taskman.finish()
        self.assertEqual(len(self.dialog.web.evaluated), accepted_count)

    def test_supported_profile_and_collection_close_hooks_are_registered(self):
        self.assertEqual(len(self.hooks.profile_will_close), 1)
        self.assertEqual(len(self.hooks.collection_will_close), 1)

    def test_normalized_study_signals_run_in_background_with_scheduler_bounds(self):
        connection = sqlite3.connect(":memory:")
        connection.executescript(
            "create table cards (id integer primary key, did integer, odid integer);"
            "create table revlog (id integer primary key, cid integer, ease integer, factor integer, type integer);"
        )
        connection.execute("insert into cards values (1, 10, 0)")
        connection.execute("insert into revlog values (1999999000, 1, 1, 2500, 1)")

        class Db:
            def all(self, sql, *args):
                return connection.execute(sql, args).fetchall()

        class Note:
            id = 50

            def items(self):
                return [("Front", "alpha")]

        class Card:
            id = 1
            type = 2
            queue = 2
            due = 9
            reps = 4
            lapses = 2

            def note(self):
                return Note()

        class Sched:
            today = 10
            dayCutoff = 2_000_000

        collection = types.SimpleNamespace(
            db=Db(),
            sched=Sched(),
            get_card=lambda card_id: Card() if card_id == 1 else None,
        )
        self.mw.col = collection
        self.dialog._on_bridge_command(json.dumps({
            "version": 2,
            "requestId": "study-2",
            "action": "loadStudySignals",
            "payload": {},
        }))
        accepted = _last_envelope(self.dialog)
        self.assertEqual(accepted["event"], "operationAccepted")
        self.mw.taskman.finish()
        completed = _last_envelope(self.dialog)
        self.assertEqual(completed["event"], "operationCompleted")
        result = completed["payload"]["result"]
        self.assertEqual(result["dayEndMs"], 2_000_000_000)
        self.assertEqual(result["signals"][0]["term"], "alpha")
        self.assertEqual(result["signals"][0]["sameDayAttempts"]["value"], 1)
        connection.close()


if __name__ == "__main__":
    unittest.main()
