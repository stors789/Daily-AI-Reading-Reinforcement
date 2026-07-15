# Changelog

Notable project changes are recorded here. DAIRR has not assigned a final public version number to the next-major release described below.

## Unreleased — next major release

### Added

- Article-based and arbitrary pasted-text translation/back-translation practice.
- Editable paragraph segmentation, complete-text practice, local draft recovery, saved practice history, attempts, revisions, reference reveal, and AI feedback.
- Versioned, atomic practice-session persistence alongside the existing article history.
- Normalized study-signal/capability models shared by AnkiConnect and add-on adapters.
- Configurable reinforcement-priority scoring, Recommended preset, Simple/Advanced controls, per-signal explanations, strict preset import/export, and FSRS-free operation.
- Manual Required, Preferred, Optional, and Excluded target plans and target-aware article generation.
- Complete visible prompt templates for six AI tasks, structured/plain-text modes, validation, exact preview, scoped overrides, and import/export.
- Capability-aware Disabled, Provider default, explicit effort, and explicit budget reasoning modes.
- Versioned asynchronous bridge operations, cancellation, stale-result protection, and explicit capability UI.
- Additive article target/reuse manifests and backward-compatible configuration schema v2.
- Android app-private offline pasted-text create/edit/segment/save/list/reopen/delete behind a versioned allow-listed bridge.

### Changed

- Standalone Anki data is normalized from standard AnkiConnect only and marks unsupported evidence unavailable.
- Add-on data access uses fresh supported collection/scheduler access behind lifecycle guards.
- Real provider failures are visible and redacted; they no longer fall back to fabricated mock success.
- Config, article, manifest, and practice writes use atomic replacement and private permissions where supported.
- The shared UI now includes Generate, Practice, Articles, Practice history, Scoring, Prompts, and API / Reasoning navigation.

### Security

- Added loopback Host/Origin checks, per-process bridge authorization token, request-size/content-type enforcement, CSP, no-store, frame denial, and related response headers.
- Removed API keys, private text, raw prompts/model responses, provider bodies, and arbitrary exception text from public diagnostics/errors.
- Add-on packaging strips credential-like config values and excludes user-owned history/practice files.

### Compatibility and limitations

- Existing Markdown articles and legacy configuration remain readable; migrations preserve unknown compatible fields.
- Standard AnkiConnect does not provide normalized FSRS values, and ordered current-day signals require trustworthy day bounds. Missing signals contribute zero and remain visible as unavailable.
- Pasted-text practice works without Anki; AI review still requires the selected model provider.
- Android intentionally has no AI provider, article history, Anki data, scoring, prompt, reasoning, generation, or save-to-card adapter in this release.
- Production signing/notarization, Windows installation, updater publication, live provider credentials, public Android packaging, and full parity must be verified separately and are not implied by source-level packaging checks.

See [release notes](docs/release-notes-next-major.md) and the [manual verification guide](docs/manual-verification.md).
