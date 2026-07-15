# ADR-0007: Normalized Anki data adapters and evidence boundaries

- Status: Accepted for platform-adapter integration
- Date: 2026-07-16
- Specification: `docs/specs/next-major-release.md`
- Extends: ADR-0003 and ADR-0004

## Context

The shared reinforcement scorer consumes `CardStudySignals`, but standalone
AnkiConnect and an in-process Anki add-on do not have equal evidence. Existing
legacy rows use `cardsInfo.reps` as `review_count`; that value is the card's
lifetime repetition count, not today's attempts. Search queries such as
`rated:1:1` prove only membership in a grade set. They do not prove event order
or repeated uses of the same grade.

The public AnkiConnect implementation exposes `version`, `findCards`,
`cardsInfo`, and the richer standard action `getReviewsOfCards`. The latter
returns timestamped revlog-shaped rows, but it does not expose the active
profile's configured Anki-day cutoff. Filtering those rows by a guessed local
midnight or rolling 24-hour window would manufacture current-day evidence.

## Decision

### Standalone AnkiConnect

1. The legacy deck/card payload remains backward compatible. In particular,
   its `review_count` continues to carry the historical `cardsInfo.reps`
   behavior until the UI contract is migrated separately.
2. `AnkiConnectDataAdapter` produces normalized card-scoped signals. It retains
   card and note identity separately and copies lifetime repetitions only into
   `metadata.lifetimeReps`; it never maps them to `same_day_attempts`.
3. `cardsInfo` supports note/card identity, fields, historical lapse count, and
   an Anki card-state classification when the relevant fields are present.
   Missing fields remain unavailable observations.
4. Standard `cardsInfo` does not expose normalized FSRS retrievability,
   difficulty, or stability. All three remain unavailable with
   `fsrs_not_available`; no value is inferred from ease factor or interval.
5. `getReviewsOfCards` is an optional richer *standard* action. It is probed
   independently and is not required for basic standalone operation. Ordered
   events, grade multiplicity, current-day attempt count, and current-day lapse
   count are emitted only when both conditions hold:
   - the action is supported and returns valid rows;
   - the caller supplies authoritative Anki-day start/end timestamps.
6. Without those bounds, grade-set searches remain useful to the legacy UI but
   are not converted to ordered `ReviewEvent` values. The normalized review
   observations explicitly report a host-mode limitation.
7. Transport errors are classified into connection failure, timeout, malformed
   response, unsupported action, incompatible version, partial response, and
   cancellation. User-facing messages are fixed and actionable; raw
   third-party error bodies are not echoed. Optional review-history failure
   degrades that capability without discarding valid `cardsInfo` signals.
8. Cancellation is cooperative around each HTTP request. The HTTP timeout is
   still the upper bound for an already-running standard-library request.

### In-process Anki add-on

9. `AnkiAddonDataAdapter` receives a collection getter rather than a collection
   object. It obtains a fresh collection for each operation and retains no
   collection, scheduler, card, note, database, window, dialog, or Qt object.
10. The caller supplies the active scheduler's authoritative study-day bounds.
    The adapter queries valid answer rows through Anki's supported collection
    database wrapper, ordered by revlog timestamp. Repeated grades and separate
    sibling cards are preserved exactly.
11. Current-day attempt count is the length of those ordered rows. Lifetime
    `card.reps` remains separate metadata. Historical lapses come from
    `card.lapses`, and review-card overdue days use `sched.today - card.due`
    only where those semantics are valid.
12. FSRS memory-state fields are optional. Valid values exposed by supported
    card/collection APIs (or an injected version-specific supported extractor)
    are emitted independently. Missing or out-of-domain values remain absent
    and do not disable non-FSRS scoring.
13. Profile closure and cancellation are explicit safe failures. The host must
    continue scheduling adapter calls off latency-sensitive UI paths and must
    discard results after profile/window teardown.

## Consequences

- Standalone and add-on scoring use one formula while explanations accurately
  reflect unequal evidence.
- Existing standalone UI payload behavior is preserved during phased
  integration, without contaminating the normalized scoring contract.
- A future standalone bridge that can authoritatively obtain the current
  Anki-day bounds can enable exact standard-action review history without
  changing the normalized domain model.
- `desktop_mock/ankiconnect_data_adapter.py` must be included in frozen desktop
  packaging alongside `ankiconnect_provider.py`.
- UI integration must perform these operations asynchronously and present the
  safe setup/troubleshooting message carried by `AnkiConnectError`.
