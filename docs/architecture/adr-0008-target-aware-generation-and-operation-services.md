# ADR-0008: Target-aware generation, response recovery, and operation services

- Status: Accepted for shared-service integration
- Date: 2026-07-16
- Specification: `docs/specs/next-major-release.md`
- Extends: ADR-0003, ADR-0004, ADR-0006

## Context

The old article path treats card values as an undifferentiated list and expects
one provider response shape. The next release needs required, preferred,
optional, and excluded learning targets while allowing grammatical inflection,
morphological changes, and reasonable equivalents. It also needs article and
pasted-text review workflows shared by the standalone application and add-on.
Model and transport failures must not leak prompts, pasted text, translations,
credentials, or raw provider bodies across either host bridge.

## Decision

1. `practice_service.py` is the host-neutral translation-practice application
   service. It composes the practice domain, editable segmentation, adjacent
   practice repository, visible prompt registry, provider capability/request
   builder, and review parser. It has no Anki, Qt, HTTP-server, or UI imports.
2. Submitting a review creates an immutable attempt before transport execution,
   so a host that opts into persistence can preserve work even when the model
   request or parsing fails. Revisions reference an earlier attempt explicitly.
   Pasted sessions may remain in memory or use local practice storage; Anki is
   never a prerequisite. Source segmentation is locked after the first attempt
   so stored feedback cannot silently become associated with different source
   text; editing then requires a new session.
3. A prepared operation carries the exact rendered messages and built provider
   request under one operation ID. Completion rejects mismatched/stale IDs.
   Persisted prompt snapshots contain task, template version, and response mode
   by default, not private rendered messages. Effective model snapshots use the
   existing redacted diagnostics representation.
4. `operations.py` provides thread-safe cooperative cancellation and optional
   abort callbacks, but does not prescribe an executor or event loop. Hosts run
   work off their UI thread. Unknown transport exception text is never exposed;
   stable public error codes and messages cross host bridges.
5. `article_generation.py` owns a typed request/result contract. Every target
   has a stable ID, trusted category, canonical text, and optional equivalent
   forms. Style is represented in the visible custom-instruction input until a
   separately versioned prompt variable is introduced. Category lists are
   rendered as JSON so IDs and equivalence hints remain machine-readable.
6. Structured results produce one outcome for every requested target: exact,
   inflected, equivalent, generically used, naturally unusable, unreported,
   excluded, or excluded-usage violation. Model claims cannot change a trusted
   target category. Optional targets may remain unreported without being forced
   into the article. Missing required/preferred usage and excluded violations
   are warnings, not crashes or silently fabricated success.
7. Plain-text mode returns useful article text and marks non-excluded target
   usage unreported. It does not pretend that target validation occurred.
8. Structured output is untrusted. Parsing accepts common provider envelopes,
   fences, wrapper prose, alternate established field spellings, partial useful
   objects, duplicate JSON fields, mapping/list usage shapes, and complete
   article fields before a malformed or truncated tail. Partial recovery uses
   only independently completed JSON strings; it never guesses or silently
   truncates article text. Invalid/unexpected mappings are counted without
   echoing their content into warnings.
9. Response and article character limits fail explicitly rather than silently
   truncating output. A finish reason indicating token exhaustion remains
   visible on a valid or partially recovered result.

## Consequences

- Standalone and add-on hosts can use identical review/generation behavior and
  choose their own background execution, storage roots, and transport adapters.
- A failed review can leave an unreviewed attempt when persistence was requested;
  this is intentional evidence of user work and enables retry/resubmission.
- Structured generation remains useful when translations or target mappings are
  absent, while diagnostics state exactly what could not be verified.
- Hosts must preserve operation IDs, ignore stale UI responses, pass cancellation
  to capable transports, and avoid logging prepared request bodies.
- The legacy article generator stays operational until host integration switches
  it to this service; this ADR does not change legacy persistence or UI files.
