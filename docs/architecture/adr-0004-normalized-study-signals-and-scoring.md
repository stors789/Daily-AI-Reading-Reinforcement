# ADR-0004: Normalized study signals, capabilities, and scoring semantics

- Status: Accepted for shared-foundation integration
- Date: 2026-07-16
- Specification: `docs/specs/next-major-release.md`
- Extends: ADR-0003

## Context

DAIRR needs one reinforcement-priority heuristic for the Anki add-on and
standalone AnkiConnect mode. The hosts do not have equal evidence. In
particular, a host may know that a card was answered with several grades but
not know their order or multiplicity; FSRS values may be absent; and current
legacy normalization sometimes merges sibling cards by note before article
selection. Treating absent data as zero would create false explanations and
different formulas in the two modes.

The score is a configurable learning-priority heuristic. It is not a
scientific estimate of intrinsic card difficulty.

## Decision

### Capability and observation semantics

1. `capabilities.py` represents runtime feature capabilities with a stable ID,
   status, reason, provenance, and optional non-sensitive detail. Available,
   temporarily unavailable, host-mode unavailable, disconnected, absent-data,
   provider-unsupported, and optional-extension-required states are distinct.
2. `study_signals.py` represents each optional datum as an `Observation`.
   Available observations require a real value. Unavailable observations carry
   no value and require a reason. Consequently, unavailable FSRS or review
   history cannot silently become zero.
3. Provenance identifies shared-core derivation, supported Anki internals,
   standard AnkiConnect, an optional AnkiConnect extension, local history,
   provider declaration, or user configuration. It is evidence, not a quality
   ranking.

### Identity and review evidence

4. A normalized card retains source ID, card ID, and note ID separately.
   Source-scoped card identity is the scoring identity. Note identity is used
   only to calculate sibling context. Cards are never merged by note before
   scoring.
5. Equivalent target text is a separate normalized target key. Duplicate
   target penalties do not change card identity.
6. Ordered same-day review history is an observation containing unique,
   ordered `ReviewEvent` values. Recovery-after-failure and repeated-failure
   contributions are available only when ordered events are available.
   Grade sets must not be represented as ordered events. A separately known
   same-day attempt count may remain available even when event order is not.
7. Scheduling and FSRS observations have validated domains: retrievability is
   0–1, difficulty is 0–10, and time values are non-negative. Hosts omit rather
   than synthesize unsupported fields.

### Scoring configuration and explanations

8. `scoring.py` defines per-signal enablement, finite weights, linear/square
   root/logarithmic/square transforms, positive input scaling, optional
   contribution floors and ceilings, and exponential age decay. Recent-reuse
   decay has full magnitude at age zero and halves at each configured
   half-life.
9. The recommended preset includes answer grades, same-day attempts,
   recovery/repeated failure, recent/historical lapses, optional FSRS values,
   elapsed/overdue time, card state, duplicate/sibling penalties, and recent
   DAIRR reuse. It exposes a small simple-control subset and complete advanced
   metadata. Reset returns a fresh recommended preset.
10. Every configured signal emits a contribution record. Records distinguish
    applied, user-disabled, and data-unavailable states and include raw value,
    transformed value, final capped contribution, reason, provenance, and a
    concise explanation. Unavailable signals contribute exactly zero.
11. Total normalization is explicit: none, clamp to 0–100, or candidate-set
    min/max to 0–100. An equal-score candidate set maps to zero because there
    is no relative distinction; this does not fabricate per-signal evidence.
12. Presets use a versioned, strict JSON representation. Unknown signal names,
    non-finite numbers, invalid types, invalid limits, and unsupported schema
    versions are rejected. Serialization contains configuration only and does
    not execute or interpolate user content.

### Target selection

13. `target_selection.py` classifies candidates as required, preferred,
    optional, or excluded after scoring. It applies threshold, category counts,
    and maximum selection count deterministically, and returns every candidate
    for preview.
14. Manual exclusion always excludes. Manual inclusion bypasses score
    threshold and is never silently discarded by the automatic maximum. If
    manual inclusions exceed that maximum, the result retains them and exposes
    `limitExceededByManual` so the UI can ask the user to resolve the conflict.
15. An explicit source-scoped card order may edit the final target order.
    Duplicate or unknown IDs are rejected rather than ignored.

## Adapter obligations

- The add-on adapter should emit ordered revlog events only from supported
  Anki APIs and preserve separate cards even when they share a note.
- The standard AnkiConnect adapter must mark order/multiplicity-dependent
  signals unavailable when its actions cannot prove them. Optional enhanced
  actions must declare optional-extension provenance and cannot become a
  standalone requirement.
- History integration should calculate article inclusion observations without
  exposing article text to scoring or logs.
- UI/application integration should use serialized score and selection
  explanations rather than recomputing formulas in JavaScript or host code.

## Consequences

- Both modes use the same formula while honestly producing different
  availability explanations.
- More add-on evidence can improve ranking without making standalone scoring
  unusable.
- Existing note-level article deduplication must move after card-level
  normalization and be expressed through target selection.
- Preset schema changes require an explicit future schema version/migration.
- The recommended numeric weights are product defaults, not scientific claims,
  and remain user-configurable.
