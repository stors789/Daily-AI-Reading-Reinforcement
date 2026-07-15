# ADR-0003: Next-major-release boundaries and compatibility invariants

- Status: Proposed
- Date: 2026-07-16
- Specification: `docs/specs/next-major-release.md`

## Context

DAIRR ships as a standalone application and an Anki add-on. Both surfaces need the same learning, translation-practice, scoring, prompt, provider, parsing, and persistence behavior, but they have different legal Anki access paths. The current repository contains shared package code, a bundled add-on core copy, desktop adapters/server code, shared web assets, and native/Tauri/Android shells. Existing article history and user configuration must remain intact.

## Decision

1. Domain and application behavior will be platform-neutral and typed where consistent with the codebase. It must not import `aqt`, Anki collection objects, Qt objects, desktop HTTP server objects, or Android-specific APIs.
2. Standalone Anki access will use standard AnkiConnect only. Missing or unsupported data will become explicit capability/unavailability states and zero scoring contribution, never fabricated values.
3. The add-on will use supported Anki APIs behind a thin lifecycle-safe adapter. It will not route through AnkiConnect when internal supported APIs are appropriate.
4. An explicit capability model will carry availability, reason, and optional-extension provenance to application services and UI. Platform-name conditionals are not a substitute for capabilities.
5. The existing history/persistence implementation remains authoritative. New practice records and reproducibility snapshots will extend it through versioned, non-destructive, unknown-field-preserving migration.
6. Provider-specific reasoning/thinking request fields remain inside provider request construction. Shared settings represent intent (`disabled`, `provider_default`, or explicit supported control); `disabled` and `provider_default` both omit parameters unless a documented provider contract requires a marker.
7. Prompt templates and all mandatory output/parser contracts are user-visible in preview. Structured and plain-text modes are explicit; custom wording is not silently altered.
8. Shared UI stays portable and obtains data/actions through a service/bridge boundary. Network/model/Anki operations are asynchronous and cancellable where supported.
9. Existing dirty user work is preserved. Exclusive ownership is required for shared config, persistence, provider abstractions, central navigation, add-on wrapper, and packaging files.

## Consequences

- Feature behavior can be tested independently from Anki and UI shells.
- Standalone scoring may have fewer signals than add-on scoring; explanations must identify exact unavailable signals.
- A temporary shared-package/bundled-add-on synchronization mechanism may remain necessary until packaging proves direct shared imports reliable.
- Persistence and prompt/provider contracts require dedicated follow-up ADRs after repository audits establish current schemas and compatibility constraints.
- UI integration occurs after shared service contracts stabilize, reducing duplicate platform logic and overlapping edits.

## Non-decisions pending audit

- Exact practice-session envelope/schema and migration version.
- Exact normalized review/scheduling signal fields supported by standard AnkiConnect.
- Whether the existing provider abstraction should be extended in place or split into capability and request-builder modules.
- Concrete approach for keeping `packages/dairr_core` and the add-on-bundled core synchronized.
