# ADR-0011: Android offline-practice production edge

- Status: Accepted for release integration
- Date: 2026-07-16
- Specification: `docs/specs/next-major-release.md`
- Extends: ADR-0003, ADR practice persistence, ADR-0010

## Context

The Android project was a secure WebView scaffold whose dispatcher rejected
every action. Its bootstrap also accepted the portable UI's third v2 envelope
argument but discarded it, so Android responses could not preserve request
identity. Embedding the Python core or reimplementing scoring, prompting, or
provider semantics in Kotlin would create a second business-logic authority.
Nevertheless, pasted-text practice is required to work without Anki, and
private drafts need durable mobile storage and lifecycle-safe dispatch.

## Decision

1. Android implements only the platform edge that is independently useful and
   authoritative today: offline pasted-text practice session creation,
   deterministic blank-line segmentation, draft saving, full segment-list
   replacement/reordering, history listing/loading/deletion, and capability
   reporting. It does not claim the Python core is embedded.
2. The WebView bridge uses v2 `{version, requestId, action, payload}` requests
   and `{version, requestId, event, payload, operationId?}` events. Legacy
   two-argument sends remain accepted, but the packaged bootstrap preserves the
   UI-generated v2 envelope. Action and identifier allow-lists and a bounded
   message size fail closed.
3. A private file repository uses one JSON document per practice session. Its
   first production schema is version 2 with an envelope-level monotonic
   revision. It begins updates from the existing JSON and overwrites only owned
   fields, preserving unknown envelope, session, and retained-segment fields.
   Unversioned development records migrate on read into a v2 envelope.
4. Persistent writes use a private same-directory temporary file, flush,
   `FileDescriptor.sync`, and atomic replace where supported, with a safe
   replace fallback and temporary-file cleanup. Android application backup is
   disabled. Record bodies and exceptions are never logged.
5. Limits are explicit and never truncate input: 50,000 source characters,
   20,000 per segment, 500 segments, and 100,000 per draft. The bridge returns
   the limits with capabilities and rejects invalid edits before persistence.
6. Client revisions use optimistic concurrency. Draft and segmentation writes
   carrying a stale revision fail actionably instead of overwriting newer
   state. Segment edits preserve retained unknown fields, validate unique safe
   IDs and contiguous order, and discard drafts only for removed segments.
7. Repository dispatch runs on a single dedicated executor so file I/O never
   blocks the WebView/UI thread and mutation ordering is deterministic. Activity
   destruction closes the dispatcher, cancels queued work, suppresses late
   emissions, removes the JavaScript interface, and destroys the WebView.
8. Saved articles, AI review/generation, Anki/FSRS/scoring, prompts, and
   reasoning remain unavailable until supported Android adapters exist. Their
   recognized actions return structured `operationFailed` results and honest
   `data_absent`, `provider_unsupported`, or mode-limitation capability states.
   Fake successes and duplicated scoring/provider formulas are forbidden.
9. The trusted UI is restricted to the AndroidX asset-loader HTTPS host and the
   `/assets/dairr/` path. File/content access, mixed content, and external
   navigation remain disabled. App-private DOM storage is enabled only because
   the portable UI uses it for draft crash recovery and user preferences.

## Consequences

- Android learners can perform and persist private pasted-text translation
  practice fully offline, including manual segmentation and history.
- Android parity is explicit rather than implied: provider/Anki-backed features
  remain visible as unavailable and guide the learner to desktop/add-on paths.
- The JSON representation follows the shared v2 practice contract conceptually
  but Kotlin does not become a second implementation of review, scoring,
  prompting, or provider behavior.
- Local practice file operations are lifecycle-cancelled, but there are no
  cancellable provider operations to expose yet; the cancellation capability
  is therefore reported as provider unsupported.
- Keystore-backed credentials, a supported mobile provider adapter, Android
  article-history interoperability, and AnkiDroid/export integration require
  future ADRs and must preserve these capability and privacy contracts.
