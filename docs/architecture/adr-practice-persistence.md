# ADR: Versioned sibling repository for translation practice

- Status: Accepted for the shared-core foundation
- Date: 2026-07-16
- Specification: `docs/specs/next-major-release.md`

## Context

DAIRR's Markdown/HTML article history is established user data and remains the
authoritative article store. Translation practice adds mutable drafts,
segmentation edits, attempts, revisions, AI feedback, and reproducibility
snapshots that do not fit safely into article front matter. Pasted text may be
private and must remain usable without Anki.

## Decision

Practice sessions use an adjacent, host-neutral JSON repository rather than
replacing or rewriting article history. Each session has a stable opaque ID and
is stored as one `practice_sessions/<id>.json` record with a versioned envelope.
Version 2 is the first supported production envelope. Readers also migrate
unversioned flat development records and version-1 `data`/`session` envelopes.

Article-backed sessions store a normalized relative article path and source and
reference snapshots. The path preserves the relationship to authoritative
history; snapshots keep the practice session usable if the article is moved or
deleted. Absolute paths and traversal components are rejected.

Writes use a same-directory private temporary file, flush and `fsync`, then
`os.replace`. A failed replacement leaves the prior record intact and removes
the temporary file. Draft/autosave data lives in the same atomic record, so a
crash cannot expose a half-written second draft format.

Known fields are normalized defensively. Corrupt optional attempts, reviews,
settings, and draft values do not make otherwise usable private source text
unreadable. Unknown envelope and nested fields survive load/save so newer or
extended writers are not destructively downgraded. A newer schema version is
rejected explicitly rather than guessed.

The repository does not log record bodies, pasted text, translations, prompts,
or feedback. Platform hosts choose the application-data root and may add
OS-specific encryption or backup policy without changing the shared schema.

## Consequences

- Existing articles are never migrated merely to enable practice.
- Pasted-text workflows and persistence have no Anki or UI dependency.
- A later index may accelerate history browsing, but individual session files
  remain authoritative and recoverable.
- Model/prompt settings may be snapshotted on individual reviews for
  reproducibility; secrets must never be included by callers.
- Repository integration must supply the correct platform application-data
  directory and reconcile article paths relative to the established article
  root.
