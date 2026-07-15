# DAIRR user guide

This guide describes the next-major DAIRR workbench as implemented in the shared web interface. Labels appear in English below because that is the source UI wording; the existing Chinese, English, and Japanese interface support remains available.

## 1. Choose the right host

DAIRR has one shared learning core but unequal host evidence.

| Area | Standalone desktop | Anki add-on |
| --- | --- | --- |
| Launch | Native Tauri window; browser/pywebview remain development fallbacks | **Tools → AI Reading Reinforcement** inside Anki |
| Anki access | Standard AnkiConnect requests only | Supported in-process Anki collection/scheduler APIs |
| Anki unavailable | Anki-backed loading/scoring/save-to-card becomes unavailable; local practice/history/settings still work | Close/profile unload cancels or detaches Anki-dependent work safely |
| Review evidence | `findCards`, `cardsInfo`, and optional standard `getReviewsOfCards`; no guessed day boundary | Ordered revlog rows within the scheduler’s authoritative Anki day |
| FSRS | Standard `cardsInfo` does not expose normalized retrievability, difficulty, or stability | Each supported FSRS value is used independently; missing values remain unavailable |
| Storage | Per-user application-data directory | Add-on `user_files` plus Anki add-on configuration |

Android uses the portable interface behind an Android-specific bridge. The current release implements app-private offline pasted-text create/edit/segment/save/list/reopen/delete with the same explicit 50,000-character source limit. Initial segmentation is deterministic at blank lines, followed by manual full-list edits/reordering; model-powered segmentation is unavailable because Android has no AI provider/review adapter. Article history, Anki/AnkiDroid data, scoring, prompt workshop, reasoning control, and save-to-card are also unavailable. Unsupported actions return a specific capability error while preserving the local draft. Consult `apps/android/README.md` and the in-app capability strip; shared HTML does not imply desktop/add-on parity.

## 2. Installation

### 2.1 Standalone macOS

When a macOS release asset is published:

1. Download the artifact for your Mac architecture from the [GitHub Releases page](https://github.com/stors789/Daily-AI-Reading-Reinforcement/releases).
2. Open the `.dmg` and drag **DAIRR** to **Applications**.
3. Launch DAIRR from Applications.
4. If you want Anki-backed workflows, install AnkiConnect in Anki and keep Anki running.

Packaging code alone is not evidence of Apple notarization. If the release notes do not explicitly say an artifact is signed and notarized, treat it as an unsigned development build. Do not normalize bypassing Gatekeeper as an installation step.

### 2.2 Standalone Windows

When a Windows release asset is published:

1. Download the Windows installer from the [GitHub Releases page](https://github.com/stors789/Daily-AI-Reading-Reinforcement/releases).
2. Run the installer and start DAIRR from the Start menu.
3. Install AnkiConnect and leave Anki running for Anki-backed workflows.

Windows packaging must be built and verified on Windows. If the release notes do not explicitly confirm Authenticode signing, SmartScreen may warn about an unsigned or low-reputation artifact.

### 2.3 Development launchers

From the repository root:

```bash
# No Anki or external provider required; suitable for UI exploration
python3 desktop_app.py --provider mock

# Standard AnkiConnect path
python3 desktop_app.py --provider ankiconnect

# Read-only AnkiConnect diagnostic
python3 desktop_app.py --provider ankiconnect --check

# Native Tauri development window
cd apps/desktop
npm install
DAIRR_DESKTOP_PROVIDER=ankiconnect npm run dev
```

The browser bridge binds to loopback only. The default application address is `http://127.0.0.1:8755`; this is not a remotely hosted web app.

### 2.4 Anki add-on

AnkiWeb installation:

1. Choose **Tools → Add-ons → Get Add-ons…**.
2. Enter `842038474` and restart Anki.
3. Open **Tools → Add-ons**, select DAIRR, and choose **Config**.
4. Configure the API key, base URL, and model for your OpenAI-compatible endpoint.
5. Choose **Tools → AI Reading Reinforcement**.

Local package installation:

```bash
python3 package_addon.py
```

Then install `dist/daily_ai_reading_reinforcement.ankiaddon` using **Tools → Add-ons → Install from file…**. Packaging sanitizes credential-like config fields and excludes the contents of `user_files`.

### 2.5 Android development build

No production Android APK is claimed by this release documentation. For a local development build, use JDK 17 and Android SDK 35:

```bash
python3 apps/android/tests/validate_scaffold.py
cd apps/android
gradle :app:testDebugUnitTest
gradle :app:assembleDebug
```

The first Gradle build can require network access for plugins/dependencies. The APK packages the shared UI, serves it from a local HTTPS asset origin, disables file/content access and mixed content, and exposes only the versioned allow-listed Android bridge. Practice JSON lives in the app-private `filesDir/practice_sessions` directory; DOM storage is used only as a local draft buffer.

## 3. AnkiConnect setup and troubleshooting

### Setup

1. In Anki, install AnkiConnect with add-on code `2055492159`.
2. Restart Anki and keep the intended profile open.
3. Leave AnkiConnect on its default loopback endpoint unless you have a reason to change it.
4. Start DAIRR with the `ankiconnect` provider.
5. Run the diagnostic before debugging the UI:

   ```bash
   python3 desktop_app.py --provider ankiconnect --check
   ```

The check verifies the endpoint/version envelope, searches current-day cards, samples `cardsInfo`, and checks the DAIRR article note type. It does not send private card text to an AI provider.

The optional write check changes Anki data:

```bash
python3 desktop_app.py --provider ankiconnect --check-write
```

It creates one suspended smoke-test note/card under a DAIRR smoke-test deck. Use it only when that write is intentional, and remove the test note afterward if it is not wanted.

### Standard actions and honest limitations

The standalone adapter uses ordinary AnkiConnect actions; no custom extension is required for core operation.

- `version` checks protocol compatibility.
- `findCards` locates rated/introduced/grade-matching candidates for legacy deck views.
- `cardsInfo` supplies card/note identity, fields, state-like queue/type values, lifetime repetitions, and lapses where present.
- `getReviewsOfCards` is probed as an optional richer standard action. Ordered current-day evidence is emitted only when valid rows **and** authoritative Anki-day bounds are available.
- Article writeback uses `createDeck`, `modelNames`/`createModel`, `addNote`, `findCards`, and `suspend`.

Important consequences:

- `cardsInfo.reps` is a lifetime repetition count, not today’s attempt count. DAIRR does not relabel it as same-day scoring evidence.
- Grade search membership such as `rated:1:1` does not prove order or multiplicity. Recovery-after-failure and repeated-failure signals remain unavailable without ordered rows and trustworthy day bounds.
- Standard `cardsInfo` does not expose normalized FSRS retrievability, difficulty, or stability. These signals are marked unavailable and contribute zero.
- Missing optional review history does not discard valid identity, lapse, card-state, duplicate, sibling, or local article-reuse evidence.
- If an existing DAIRR note type is missing required fields, diagnostics report it; the saver does not silently rewrite the note type.

### Failure guide

| Symptom | What to check | Fallback |
| --- | --- | --- |
| Connection refused | Anki is running, profile is open, AnkiConnect is enabled, endpoint is `127.0.0.1:8765` | Continue pasted practice; retry Anki actions later |
| Timeout/stale connection | Restart Anki/AnkiConnect; check local security software; retry | Cancel in DAIRR; an already-running HTTP call may take until its finite timeout |
| Incompatible/unsupported action | Update AnkiConnect; run `--check` | Core card data continues if the failed action was optional |
| Malformed or partial response | Update/restart AnkiConnect and inspect only safe public error codes | No missing field is fabricated; other available signals remain usable |
| No cards today | Confirm the active Anki profile and Anki-day timing | Paste text or select an existing article instead |
| Save-to-card fails | Run `--check`; verify note-type fields and deck permissions | Article Markdown/HTML history remains local even when writeback fails |

Raw AnkiConnect/provider bodies are not shown in bridge errors. This protects private fields, but it means troubleshooting should begin with the diagnostic command and stable public error classification.

## 4. Workbench navigation

The top navigation contains **Generate**, **Practice**, **Articles**, **Practice history**, **Scoring**, **Prompts**, and **API / Reasoning**. A capability strip summarizes the current host/provider state. A limited count is not necessarily a global failure: the affected workspace and its evidence/error text distinguish disconnection, host-mode limits, absent FSRS data, provider limits, or an optional dependency.

Long Anki/provider operations return immediately to the UI and continue asynchronously. **Cancel** is cooperative. A queued operation cancels promptly; a blocking standard-library network request can remain pending until its timeout. Late or stale completions are ignored by request/operation identity.

## 5. Translation and back-translation practice

### Pasted text

1. Open **Practice** and choose **Pasted text**.
2. Paste or write source prose. The explicit limit is 50,000 characters; text over the limit is rejected, not truncated.
3. Enter **Source language** (`auto` is allowed), **Target language**, **Direction**, optional proficiency, and optional review instructions.
4. Choose **Create practice**.

Paragraph breaks form the initial segments. Before the first review attempt, use **Split**, **Merge next**, the arrow buttons, or edit **Source segment** directly. Once an attempt exists, segmentation is locked so older feedback cannot become attached to different source text; create a new session if the source structure must change.

Pasted sessions begin as local work. Browser-local recovery protects a newer unsaved draft, while **Save session** writes the complete versioned session to DAIRR’s local practice history. Saved sessions appear under **Practice history**.

### Existing DAIRR article

1. Open **Practice**, choose **DAIRR article**, and select an item from saved article history.
2. Choose **Source → target** or **Back-translation**.
3. Set the language pair and choose **Create practice**.

DAIRR reads the existing Markdown article rather than creating a second article store. Where `[T]` translations exist, source-to-target practice uses the article paragraph as source and its translation as a reference. Back-translation reverses those roles. The saved source/reference snapshots keep the session usable if the article is later moved or deleted.

Choose **Reveal reference** only when you want the comparison. A reference is an additional stylistic and meaning comparison point, never the only valid answer.

### Segment and complete-text behavior

- **One segment** stores a draft for the selected segment. The rail moves among segments and shows draft/review state.
- **Complete text** uses the combined source and a separate full-text draft.
- **Review translation** creates an immutable attempt before provider transport. If the provider request fails, the attempted work can still be preserved when the session is saved.
- Feedback can include meaning, omissions/additions, grammar, vocabulary, naturalness, register/style, a summary, score, and suggested revision. Categories may be partial when a provider returns only a useful subset.
- **Revise and resubmit** keeps earlier attempts visible and links the revision to its predecessor.

The reviewer is instructed to distinguish real errors from valid alternatives, avoid literal reconstruction, and evaluate directly against the source when no reference exists. Custom review instructions and proficiency are included in the visible prompt inputs.

AI review requires a configured provider. Drafting, segmentation, save/reopen, and reference reveal do not require Anki. Submitting a review sends the relevant source, user translation, and configured instructions to the selected provider.

## 6. Reinforcement scoring and targets

DAIRR’s score is a configurable **reinforcement-priority heuristic**, not a scientific measurement of intrinsic card difficulty.

### Recommended preset and modes

Open **Scoring**. The **Recommended** preset supplies defaults for:

- Again, Hard, Good, and Easy answer counts;
- same-day attempts, recovery after failure, and repeated failure;
- recent and historical lapses;
- low FSRS retrievability, FSRS difficulty, and low stability;
- elapsed and overdue days;
- new/learning/relearning/review card state;
- equivalent-target duplicates and sibling cards;
- recent DAIRR reuse and recent inclusion count.

**Simple** shows the highest-value signal rows. **Advanced** exposes every signal’s enable toggle, weight, and linear/square-root/logarithmic/square transform. The versioned preset format also supports normalization divisors, contribution floors/ceilings, and optional half-life decay for compatible imported presets. Reset restores a fresh recommended preset.

Selection controls set minimum inclusion score, maximum cards, Required/Preferred/Optional counts, and total normalization (`None`, `Clamp 0–100`, or candidate `min–max`). Candidate min–max maps an equal-score set to zero because there is no relative distinction.

Preset import/export is strict, versioned JSON. Invalid signal names, types, limits, non-finite numbers, and unsupported schema versions are rejected rather than guessed.

### Preview and manual control

Choose **Preview candidates**. Each row shows:

- whether it is included;
- the candidate/term and total priority;
- its Required, Preferred, Optional, or Excluded category;
- a details list counting applied contributions and unavailable signals.

Open **Evidence** to inspect each signal’s status, contribution, and unavailability reason. Unavailable evidence contributes exactly zero; a user-disabled signal is distinct from an unavailable one. Change the checkbox/category to force inclusion or exclusion. Manual inclusion bypasses the threshold and is not silently removed by the automatic maximum; if manual choices exceed the maximum, resolve that conflict in the plan.

Choose **Use target plan** to send the current categories/order to **Generate**. Required targets have the strongest inclusion intent, followed by Preferred. Optional targets may be omitted for naturalness. Excluded targets are not learning targets and unexpected use is reported. Grammatical inflection and reasonable equivalent forms are allowed; target outcomes/warnings identify missing or unexpected usage instead of pretending every string was inserted.

## 7. Prompt workshop

Open **Prompts**. The **Task** menu covers:

- Article generation
- Translation review
- Back-translation review
- Target usage validation
- Text segmentation
- Preprocessing

For each task, edit the complete **System prompt**, **User prompt template**, **Response mode**, and **Visible response contract**. Override precedence is **Current API profile**, then **Current provider**, then **Project default**.

The documented variable chips are task-specific. Across the registry they include source text/languages, target language, proficiency, selected/required/preferred/optional/excluded targets, user and reference translations, genre, desired length, custom/segmentation instructions, and `output_format_contract`.

Template rules:

- Use `{variable_name}` for a documented value.
- Use `{{` and `}}` for literal braces.
- Attribute/index access, conversions, format specifications, unknown variables, missing referenced values, and unmatched braces fail before network I/O.
- **Structured output** requires a non-empty visible contract and `{output_format_contract}` in the visible system or user template.
- **Plain text** does not require structured parsing.
- DAIRR does not silently append substantive hidden instructions after rendering.

Choose **Render exact preview** to inspect the actual system/user messages, visible response contract, and effective non-secret request settings. Preview intentionally contains the private content you supplied for that request; it is displayed locally but excluded from ordinary logs and diagnostics. **Import**, **Export**, and **Reset task** operate on versioned prompt mappings.

## 8. API and reasoning

Use **API / Reasoning → Edit API profile** for provider credentials/model settings. Reasoning intent has three distinct modes:

- **Disabled:** omit every reasoning/thinking parameter. It is not converted to a “minimal” effort.
- **Provider default:** omit an explicit override unless a provider capability contract requires a default marker.
- **Explicit:** send one supported named effort **or** token budget through the provider’s known dialect.

Current conservative mappings are:

| Provider ID | Explicit control | Wire dialect |
| --- | --- | --- |
| OpenAI | `minimal`, `low`, `medium`, `high` effort | `reasoning_effort` |
| OpenRouter | `minimal`, `low`, `medium`, `high` effort | `reasoning.effort` |
| Anthropic | token budget, minimum 1024 | `thinking` budget |
| Gemini | non-negative token budget | Gemini thinking config |
| DeepSeek, Qwen, custom/unknown | No explicit control is assumed | No guessed field |

Provider capability validation prevents effort-plus-budget combinations, unsupported values, managed-field overrides, and incompatible sampling/response-format/streaming combinations. For example, a known OpenAI/Anthropic explicit-reasoning request with incompatible temperature/top-p settings is rejected before network I/O rather than sending a contradictory body.

Choose **Preview effective settings** to see model, output limits, response mode, supported reasoning intent, and safe extra-field names. API keys, messages, prompt content, and private advanced values are excluded.

## 9. Articles and reading

The existing article workflow remains available:

- select a source/deck and card fields;
- filter/select current-day cards or use a scoring target plan;
- generate by language, level, genre/style, length, and custom instruction;
- read horizontally or in Japanese vertical mode;
- reveal paragraph translations individually;
- export the saved article;
- browse the activity history by day/deck;
- save a suspended reading card back to Anki where the host capability permits it.

Markdown is the authoritative article record. New target-aware articles also receive an adjacent `.manifest.json` with target identities, target usage/outcomes, unused targets, and reuse metadata. Old Markdown without a manifest remains readable.

![Japanese vertical reading with an expanded inline translation](../assets/dairr-vertical-reading-cyber-violet.png)

The screenshots above cover the preserved reading/generation surfaces. Updated Practice, Scoring, Prompts, and API/Reasoning screenshots should be added after the final cross-platform visual acceptance pass; no placeholder image is presented as tested UI evidence.

## 10. Local data, migration, backup, and recovery

### Standalone locations

| Data | macOS | Windows |
| --- | --- | --- |
| App root | `~/Library/Application Support/DAIRR/` | `%APPDATA%\DAIRR\` |
| Config | `config.json` under app root | `config.json` under app root |
| Articles | `articles/` under app root | `articles\` under app root |
| Practice | `practice_sessions/` under app root | `practice_sessions\` under app root |

If legacy `~/.dairr_config.json` exists, standalone mode intentionally continues using it. `DESKTOP_CONFIG_PATH` and `DESKTOP_OUTPUT_DIR` can override the defaults.

### Add-on locations

- Anki manages the add-on `config.json`.
- Articles live under `addon/daily_ai_reading_reinforcement/user_files/articles/`.
- Practice sessions live under `addon/daily_ai_reading_reinforcement/user_files/practice_sessions/`.

The add-on package excludes user content, but a manual uninstall/deletion of the add-on folder can still remove local files. Back up `user_files` before replacement, profile moves, or manual cleanup.

### Android location

Android saved pasted sessions live in the application-private `filesDir/practice_sessions` directory as one versioned JSON record per session. Application backup is disabled and this release has no session export, so uninstalling DAIRR or clearing its storage deletes these records. Treat them as device-local practice drafts, and copy important source/translation text elsewhere before either action. DAIRR does not expose the directory to the WebView or external pages.

### Migration behavior

- Config schema v2 adds prompt scopes, reasoning intent, and scoring presets. Unknown top-level/profile/extension fields survive round trips. Invalid optional release fields fall back independently; credentials and legacy settings are retained.
- Practice schema v2 reads flat development records and v1 `data`/`session` envelopes. Known fields are normalized, corrupt optional attempts/reviews are isolated where possible, unknown fields survive save, and a newer unsupported schema is rejected instead of guessed.
- Existing Markdown articles are never bulk-rewritten to enable practice. Article-backed practice stores a relative reference plus source/reference snapshots.
- Article manifests are additive. Old articles remain valid without one.
- Config, practice, article, and manifest writes use same-directory temporary files and atomic replacement where the platform permits it. This prevents half-written replacement files; it is not a versioned backup system.

### Backup and recovery

1. Close DAIRR and, for add-on data, close Anki.
2. Copy the complete desktop DAIRR app-data root or the add-on `user_files` directory plus its config to a protected backup.
3. Preserve file names and relative directories when restoring.
4. If one practice JSON file is corrupt, move a copy aside for inspection rather than editing the only copy. Other per-session files remain independently listable.
5. If config is unreadable, DAIRR uses safe defaults and records a non-secret warning; the corrupt file is not silently overwritten merely by loading it. Restore a known-good copy or fix valid JSON without adding secrets to issue reports.

DAIRR does not encrypt these local files. Use full-disk encryption, OS account protections, and encrypted backups when the content is private.

## 11. Privacy and local bridge security

- API keys stay in local config and are sent only as authorization to the configured endpoint. Desktop config and practice temporary files request owner-only permissions on POSIX; Windows relies on the application-data directory ACL.
- Pasted text, articles, translations, feedback, full prompts, raw model output, and provider response bodies are excluded from normal logs, diagnostics, exception messages, and bridge errors.
- Exact prompt preview is an intentional local display. Do not include it in screenshots or bug reports when it contains private text.
- Submitting generation/review sends the necessary content to the AI provider you selected. Review that provider’s retention/privacy policy; DAIRR cannot impose local-only handling on a remote service.
- The standalone bridge binds only to loopback, validates `Host` and exact loopback `Origin`, requires JSON and a request-size limit, and protects POSTs with a high-entropy per-process token. Responses use a restrictive content-security policy and no-store headers.
- The bridge token protects against ordinary drive-by browser requests; it is not an OS sandbox against another process running as the same user.
- Do not share config files, practice JSON, article history, raw prompt previews, bridge tokens, or updater private keys.

## 12. Known limitations

- Standalone scoring is useful with partial evidence but cannot match in-process add-on review/FSRS visibility through standard AnkiConnect.
- Cooperative cancellation cannot forcibly interrupt every blocking HTTP implementation; the configured timeout is the hard bound.
- Model output is untrusted. DAIRR recovers common wrappers/fences/partial structured content, but invalid or truncated results can still produce a visible error or warnings.
- Public macOS/Windows signing, notarization, installer reputation, and live updater publication require credentials and platform-specific release validation. Source configuration does not prove those steps occurred.
- Android is currently an offline pasted-practice edge, not a provider/Anki/article/scoring/prompt parity build. No public production APK or device acceptance is claimed here.
