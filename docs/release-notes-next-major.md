# Next-major release notes

Status: **unreleased**. This document describes the implemented release scope in the repository. It does not claim that signed macOS/Windows installers, a production Android package, or live-provider parity have been published or certified.

## What’s new

### Translation studio

- Create practice from arbitrary pasted text or an existing DAIRR article.
- Choose source/target languages, source-to-target or back-translation direction, optional proficiency, and custom review instructions.
- Segment by paragraph, then edit, split, merge, and reorder before the first attempt.
- Work on one segment or the complete text; preserve separate drafts.
- Reveal saved article references on demand without treating them as canonical answers.
- Submit reference-free or reference-aware AI review, retain attempts, and revise/resubmit.
- Autosave locally and persist selected sessions in an adjacent versioned history repository that works without Anki.
- Reject over-limit source/model output explicitly instead of silently truncating it.

### Reinforcement scoring and target planning

- One platform-neutral score engine for add-on and standalone data.
- Configurable enablement, weights, transforms, normalization, floors/ceilings, and decay for 19 answer/scheduling/FSRS/identity/reuse signals.
- Recommended preset with Simple and Advanced views, reset, and strict JSON import/export.
- Per-card totals and applied/disabled/unavailable contribution explanations.
- FSRS-free operation: missing values contribute zero and remain visibly unavailable.
- Manual inclusion/exclusion and Required, Preferred, Optional, Excluded categories.
- Natural target-aware generation with inflection/equivalent handling, structured usage mapping, and warnings for missing or unexpected usage.

### Prompt and provider control

- Complete task templates for article generation, translation review, back-translation review, target validation, text segmentation, and preprocessing.
- Editable system and user templates, documented variables, literal-brace validation, structured/plain-text modes, and visible response contracts.
- Project/provider/profile override scopes, exact rendered preview, reset, and versioned import/export.
- Reasoning intents distinguish Disabled, Provider default, and explicit supported effort/budget.
- Known OpenAI, OpenRouter, Anthropic, and Gemini request dialects; conservative no-guess behavior for DeepSeek, Qwen, and unknown compatible providers.
- Safe effective-setting diagnostics that omit keys, messages, prompts, and private advanced values.

### Dual-host reliability

- Bridge protocol v2 with request/operation identity, bounded background execution, polling, cooperative cancellation, stale-result protection, and privacy-safe errors.
- Standalone uses standard AnkiConnect only and classifies connection, timeout, malformed, unsupported, incompatible, partial, and cancelled requests.
- Add-on obtains fresh collection references per operation and guards profile close, collection unload, dialog destruction, and background callbacks.
- Explicit capability statuses distinguish available, temporary, host-mode, disconnected, absent-data, provider-unsupported, and optional-dependency states.
- Real-provider failures no longer become fabricated mock success. Demo/mock output requires explicit mock selection.

### Android offline edge

- Added a versioned Android bridge-v2 envelope and allow-list behind the shared UI.
- Added app-private, atomic, per-session JSON storage for offline pasted-text practice.
- Android can create, edit/segment, save drafts/sessions, list, reopen, and delete pasted sessions with explicit source/segment/translation limits and stale-revision checks.
- External navigation, file/content access, and mixed content remain blocked; WebView/bridge work is torn down with the Activity.
- AI review/providers, article history, Anki/AnkiDroid data, scoring, prompts, reasoning, generation, and save-to-card fail closed with actionable capability messages in this release.

### Persistence and security

- Backward-compatible config schema v2 with unknown-field preservation.
- Atomic, private config/practice/article/manifest writes where supported.
- Practice schema v2 with v0/v1 readers, stable IDs, relative article references, snapshots, corrupt-optional-field tolerance, and unknown-field retention.
- Existing Markdown remains authoritative; additive article manifests record target/reuse metadata.
- Standalone loopback bridge now validates Host/Origin, requires a per-process token, limits request bodies, and applies CSP/no-store/security headers.
- API keys, private text, translations, prompts, provider bodies, and raw exceptions are excluded from normal diagnostics and public errors.

## Preserved behavior

- Current-day deck/card selection and card-field configuration.
- Article generation, saved article activity history, filtering, and read-only reopen.
- Horizontal and Japanese vertical reading.
- Paragraph-by-paragraph translation reveal.
- Article Markdown/HTML export.
- Suspended reading-card creation through the applicable Anki host.
- OpenAI-compatible profiles, model discovery, UI language, themes, and generation presets.

## Compatibility notes

- Standalone does not use or bundle Anki’s internal Python/Qt APIs.
- `cardsInfo.reps` remains lifetime metadata, not fabricated same-day scoring evidence.
- Standard AnkiConnect does not expose normalized FSRS values. Exact ordered-day signals require both valid richer action rows and authoritative Anki-day bounds.
- The add-on can provide ordered revlog and optional supported FSRS evidence while a profile is open, so score explanations may differ even though the formula is shared.
- Pasted practice remains available when Anki is closed. AI review still needs the selected provider.

## Migration and backup

No destructive bulk article migration is performed. Before upgrading a personally important installation, close DAIRR/Anki and back up:

- standalone: the full DAIRR application-data directory and any legacy `~/.dairr_config.json`;
- add-on: `addon/daily_ai_reading_reinforcement/user_files/` and the add-on configuration.

See [Local data, migration, backup, and recovery](user-guide.md#10-local-data-migration-backup-and-recovery).

## Distribution status and remaining risk

- The credential-free `python3 scripts/desktop_release.py pre-publish` gate covers release metadata/secrets, production compile/import, the full unit suite, add-on package privacy, portable UI/JavaScript, Android static validation, desktop packaging dry-runs, Tauri environment reporting, and locked Rust compilation.
- A real macOS ARM onedir sidecar has passed runtime-entry validation and command-line smoke testing, and its manifest includes the shared core, web assets, and normalized AnkiConnect adapter without private/cache/output/log/database content. A Tauri `--no-bundle` build has also passed in that environment.
- Release packaging and source-level updater checks do not prove public signing/notarization.
- macOS and Windows artifacts must be built and smoke-tested on their target platforms, signed with release credentials, and verified after installation before they are described as production releases.
- The current local environment did not have Xcode, macOS Intel/Windows hosts, or signing credentials. Full DMG/NSIS signing, Apple notarization, and installed updater tests therefore remain unverified locally and belong to the native CI/release-credential pass.
- Live Anki, AnkiConnect, MoMo, and third-party AI behavior depends on installed versions, credentials, network access, and provider contracts. Mocked automated coverage is not a substitute for final credentialed smoke tests.
- Android static validation covers its bridge/assets/repository boundary, but no public production APK or complete device acceptance is claimed. It is intentionally limited to offline pasted-text persistence; shared UI assets do not prove parity.
- The committed JDK 17 SDK-free harness compiles the actual Android bridge, dispatcher, and repository production sources; it validates and reports the local Gradle version, while CI pins the canonical Gradle 8.10.2 toolchain. All seven JVM tests and the static validator passed in the current environment. A clean first run resolves pinned build/test dependencies from public repositories. Android SDK assembly and device testing remain unverified because that environment has no Android SDK.

Use the [manual verification guide](manual-verification.md) for the release-candidate acceptance pass.
