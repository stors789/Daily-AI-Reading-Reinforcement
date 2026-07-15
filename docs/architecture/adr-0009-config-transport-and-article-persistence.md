# ADR-0009: Non-destructive config, real provider transport, and article manifests

- Status: Accepted for release integration
- Date: 2026-07-16
- Specification: `docs/specs/next-major-release.md`
- Extends: ADR-0003, ADR-0006, ADR-0008

## Context

DAIRR's existing JSON configuration contains local credentials, named provider
profiles, article presets, and host-specific extensions. Existing article
history is Markdown plus rendered HTML. The prompt/provider foundations added
validated templates and request builders, but the production HTTP path still
constructed a separate hidden prompt and request body. Desktop article saving
also temporarily mutated the process-global article directory, making
concurrent adapters unsafe.

## Decision

1. Configuration schema version 2 is a non-destructive normalization layer over
   the existing mapping. It adds task/provider/profile prompt overrides,
   reasoning intent, and scoring presets. Known values are validated
   independently; unknown top-level and nested extension fields, named-profile
   fields, and local credentials survive round trips. Invalid optional release
   fields fall back without making legacy configuration unreadable.
2. Disabled and provider-default reasoning remain distinct persisted values.
   Explicit effort or budget values are converted to the capability-aware
   provider dialect only by the shared request builder. Invalid stored intent
   falls back to provider default and is never guessed into a wire field.
3. Desktop config writes use a same-directory private temporary file, flush,
   `fsync`, and atomic replacement. Config files use owner-only permissions.
   A read-only host retains an in-memory `config_save_warning`; it must not
   claim that persistence succeeded in a future UI acknowledgement.
4. The real OpenAI-compatible transport consumes `RenderedPrompt.messages` or
   an already built `BuiltProviderRequest` unchanged. It appends no prompt
   suffix. Structured response format, sampling, reasoning, and advanced-body
   conflicts are decided before HTTP I/O by provider capabilities. Temperature
   zero is preserved.
5. Provider response bodies, authorization values, and prompts are excluded
   from transport errors. Network errors use an allow-listed classification.
   The transport supports a finite timeout and cooperative cancellation before
   and after blocking I/O; shared operation services can use the same transport.
6. Markdown remains the authoritative article-history record. New articles add
   a versioned adjacent `.manifest.json` containing target identities, actual
   usage, unused targets, and reuse metadata. Unknown manifest fields survive
   atomic updates, while credential-like fields are rejected. Old Markdown
   without a manifest remains readable unchanged.
7. Article auxiliary files and the authoritative Markdown are written
   atomically, with Markdown replaced last. Every host passes its article root
   explicitly; desktop adapters never mutate the process-global compatibility
   default. Load/update/delete validate resolved containment and reject prefix
   and symlink escapes.

## Consequences

- Existing add-on and standalone configuration remains usable while new hosts
  can expose prompt, scoring, and reasoning settings incrementally.
- A future schema may add fields without an older DAIRR release erasing them.
- Prompt preview and wire content have one source of truth; safe diagnostics
  can show effective non-secret settings separately.
- Article reuse/scoring can consume machine-readable historical target usage
  without parsing prose or rewriting legacy history.
- Cooperative cancellation cannot forcibly abort every `urllib` implementation
  while blocked; the timeout is the hard upper bound and cancellation is
  rechecked immediately after I/O.
