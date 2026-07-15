# Daily AI Reading Reinforcement

**Turn today’s flashcards—and any text you care about—into deliberate reading and translation practice.**

DAIRR is a shared learning workbench delivered as an Anki add-on and a standalone desktop app. It can rank cards reviewed during the current Anki day, turn selected targets into a natural reading article, and review translations from either saved DAIRR articles or arbitrary pasted prose. The same core scoring, practice, prompt, provider, parsing, and persistence logic serves both hosts; each host reports unavailable capabilities instead of inventing data.

![DAIRR generation workspace using the Cyber Violet theme](assets/dairr-workspace-cyber-violet.png)

## Highlights

- **Two practice paths:** open a saved DAIRR article or paste up to 50,000 characters of your own text. Work one segment at a time or on the complete text, reveal a reference when one exists, and revise after AI feedback.
- **Transparent reinforcement priority:** rank candidates with configurable answer, lapse, scheduling, duplicate, sibling, and recent-reuse signals. Every signal is applied, disabled, or explicitly unavailable; unavailable evidence contributes zero.
- **Editable target plan:** preview candidates, inspect contribution counts, include or exclude cards, and classify targets as Required, Preferred, Optional, or Excluded before generation.
- **Natural target-aware generation:** required and preferred targets receive priority, optional targets may be omitted, excluded targets are guarded against, and structured response failures are recovered defensively where possible.
- **Visible AI contracts:** edit the system prompt, user template, response mode, and response contract for article generation, translation review, back-translation review, target validation, segmentation, and preprocessing. Preview the exact rendered messages before sending.
- **Provider-aware reasoning:** choose Disabled, Provider default, or a capability-validated explicit effort/budget. Disabled sends no reasoning or thinking parameter.
- **Reading and history:** keep horizontal and Japanese vertical reading, paragraph-by-paragraph translation reveal, article export, activity history, and suspended Anki reading-card creation.
- **Offline from Anki:** pasted-text drafting, segmentation, local history, and prompt/scoring configuration remain usable when Anki or AnkiConnect is unavailable. AI review still requires a configured model provider and network access unless the provider is local.

## Product surfaces

| Capability | Standalone desktop | Anki add-on | Android |
| --- | --- | --- | --- |
| Pasted-text practice | Yes; no Anki required | Yes; no collection data required | Offline create/edit/segment/save/reopen/delete |
| Saved-article practice and history | Local desktop app-data | Add-on `user_files` | Pasted sessions only; article history unavailable |
| Anki data | Standard AnkiConnect only | Supported in-process Anki APIs | Unavailable in this release |
| Ordered current-day review evidence | Limited; only when a standard action and authoritative Anki-day bounds are available | Yes while a profile/collection is open | Unavailable in this release |
| FSRS values | Not exposed by standard `cardsInfo`; shown unavailable | Used only when supported values are present | Unavailable in this release |
| Save suspended reading cards | Through AnkiConnect when connected/configured | Through Anki APIs | Unavailable in this release |
| Prompt customization, AI review, generation, reasoning | Yes | Yes | No Android provider adapter in this release |
| Cancellation | Cooperative; an active network call may finish at its timeout | Cooperative and lifecycle-aware | Local I/O is lifecycle-cancelled; no provider operation exists |

The standalone application never imports Anki’s internal Python or Qt objects. AnkiConnect failure reduces only Anki-backed features; it does not disable pasted-text practice.

## Install

### Anki add-on

From AnkiWeb:

1. In Anki, choose **Tools → Add-ons → Get Add-ons…**.
2. Enter **`842038474`**.
3. Restart Anki.
4. Choose **Tools → Add-ons**, select DAIRR, and open **Config** to set an OpenAI-compatible API key, base URL, and model.
5. Open **Tools → AI Reading Reinforcement**.

For a local build, run `python3 package_addon.py`, then install `dist/daily_ai_reading_reinforcement.ankiaddon` with **Tools → Add-ons → Install from file…**. The package builder strips credentials and private practice/history data.

### Standalone macOS and Windows

Use a matching asset from the project’s [GitHub Releases page](https://github.com/stors789/Daily-AI-Reading-Reinforcement/releases) **only when one is published for your platform**:

- macOS: open the `.dmg`, drag DAIRR to Applications, then launch DAIRR.
- Windows: run the published installer and launch DAIRR from the Start menu.

Public signing/notarization has not been proven merely by the presence of packaging code. An unsigned development build can trigger macOS Gatekeeper or Windows SmartScreen; do not bypass an unexpected warning unless you built the artifact yourself or verified its release provenance.

To use Anki-backed features, install AnkiConnect (`2055492159`), restart Anki, and leave Anki running. The default endpoint is `http://127.0.0.1:8765`.

For development instead of a published installer:

```bash
# Browser fallback
python3 desktop_app.py --provider mock
python3 desktop_app.py --provider ankiconnect

# Preferred native development shell
cd apps/desktop
npm install
npm run dev
```

See the [user guide](docs/user-guide.md) for full installation, AnkiConnect troubleshooting, practice/scoring/prompt/reasoning instructions, capability differences, privacy, and backup/recovery.

The Android project now provides app-private offline pasted-text sessions, but no published production APK, AI provider, article history, Anki adapter, scoring, prompt workshop, or reasoning control. Developers can validate it with `python3 apps/android/tests/validate_scaffold.py`; see `apps/android/README.md` for the target build instructions.

## First run

1. Open **API / Reasoning → Edit API profile** and configure the provider, base URL, model, and local API key.
2. Choose **Disabled** or **Provider default** reasoning unless the capability badge offers a validated explicit control.
3. For Anki-backed generation, start Anki and select a deck in **Generate**. Open **Scoring**, choose **Preview candidates**, adjust the target categories, then choose **Use target plan**.
4. For Anki-independent practice, open **Practice → Pasted text**, enter a target language, and choose **Create practice**.

## Documentation

- [Complete user guide](docs/user-guide.md)
- [Next-major release notes](docs/release-notes-next-major.md)
- [Manual verification guide](docs/manual-verification.md)
- [Standalone provider and diagnostics reference](docs/desktop_standalone.md)
- [Packaging guide](docs/packaging.md)
- [Desktop updater and signing requirements](docs/desktop_auto_updates.md)
- [Changelog](CHANGELOG.md)

## Development and checks

Python 3.11 or newer is recommended.

```bash
python3 -m unittest discover -s tests
python3 -m compileall .
python3 package_addon.py
python3 package_desktop.py --entry browser --dry-run
python3 package_desktop.py --entry native --dry-run
python3 package_tauri_sidecar.py --dry-run
python3 apps/android/tests/validate_scaffold.py
python3 scripts/desktop_release.py pre-publish
```

`pre-publish` is the credential-free consolidated release gate. It covers metadata/secret checks, compile/import, the full unit suite, add-on privacy, portable UI/JavaScript checks, Android static validation, desktop dry-runs, Tauri environment info, and locked Rust compilation. Build commands still validate only the environment in which they run: a macOS build does not prove Windows packaging, and an unsigned bundle does not prove distribution signing.

The canonical shared package is `packages/dairr_core/src/dairr_core/`. The Anki wrapper is isolated under `addon/daily_ai_reading_reinforcement/`; the standalone bridge and adapters are under `desktop_mock/`; the portable UI is under `addon/daily_ai_reading_reinforcement/web/`.

## Privacy and issue reports

DAIRR stores configuration and history locally. Text is sent to the AI endpoint you configure only when an AI operation is submitted. API keys, pasted text, translations, prompts, private articles, and raw provider responses are excluded from normal diagnostics and bridge errors; local files are not encrypted by DAIRR, so protect your operating-system account and backups.

When reporting a provider issue, share effective non-secret settings and public error codes—not configuration files, practice-session JSON, raw prompts, tokens, or private text.
