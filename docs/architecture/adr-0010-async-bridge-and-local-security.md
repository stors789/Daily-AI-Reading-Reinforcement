# ADR-0010: Versioned asynchronous host bridge and local transport security

- Status: Accepted for release integration
- Date: 2026-07-16
- Specification: `docs/specs/next-major-release.md`
- Extends: ADR-0003, ADR-0007, ADR-0008, ADR-0009

## Context

The portable UI previously sent unversioned `{action, payload}` objects. The
standalone HTTP handler executed every action on a request thread and returned
raw legacy events. It had no request identity, operation registry,
cancellation, response-order protection, origin policy, or bridge
authorization. Several branches returned raw configuration or exception text,
and real provider failure could silently become a mock article success.

The browser fallback, pywebview, Tauri, and add-on still need one portable
contract. Pasted-text practice must remain usable when AnkiConnect is absent,
while provider and Anki operations must not block a UI thread.

## Decision

1. Bridge protocol version 2 uses request envelopes
   `{version, requestId, action, payload}` and response envelopes
   `{version, requestId, operationId?, event, payload}`. Legacy requests without
   a version or request ID are accepted during migration and receive a v2
   response with a generated ID.
2. `bridge_contract.py` is the host-neutral authority for supported release
   actions, synchronous event names, operation event names, envelope parsing,
   and privacy-safe failures. Both hosts preserve request IDs. A UI discards a
   completion when its request ID no longer owns the relevant view state.
3. Long provider and Anki operations return `operationAccepted` immediately.
   A bounded executor runs at most four concurrent operations. The registry
   retains a finite, TTL-pruned set of terminal records. Polling returns
   `operationProgress`, `operationCompleted`, `operationFailed`, or
   `operationCancelled`; terminal payloads retain the original request ID and
   nest the result under `payload.result`.
4. `cancelOperation` is idempotent. Cancellation is cooperative through the
   shared token. Queued work is cancelled immediately; a blocking standard
   library network call remains bounded by its finite transport timeout.
5. Unknown exception text never crosses the bridge. Errors contain only a
   stable code, allow-listed public message, retryable flag, and safe scalar
   details. Raw provider bodies, prompts, pasted source text, translations,
   credentials, filesystem paths, and arbitrary exception strings are not
   logged or returned.
6. The standalone server binds only to a loopback address. It validates the
   HTTP `Host` header against loopback names and accepts browser origins only
   from its exact loopback origin. CORS never uses a wildcard.
7. Every bridge POST requires a high-entropy per-process token injected into
   the same-origin application page and sent in `X-DAIRR-Bridge-Token`.
   Requests also require JSON content type and an explicit body-size limit.
   Health checks disclose that a token is required but never disclose it.
   The independently generated Tauri shutdown token remains a separate,
   single-purpose credential.
8. Responses use no-store caching, MIME-sniffing protection, frame denial,
   no-referrer policy, and a restrictive CSP compatible with the current
   inlined portable UI. Static UI and health requests receive the same Host
   validation.
9. The injected browser bridge supports `sendRequest(envelope)` and the legacy
   `send(action, payload, envelope?)`. It delivers accepted/progress/terminal
   events to the portable receiver and polls asynchronously without blocking
   the page.
10. Static/local practice, config editing, prompt preview, and history actions
    do not probe Anki. Normalized Anki signals are fetched only by explicit
    asynchronous actions. Standard AnkiConnect review events remain
    unavailable unless the caller explicitly supplies authoritative Anki-day
    bounds; a configurable local clock is not relabeled as authoritative.
11. Mock generation is allowed only when the user explicitly selected the demo
    provider. A failure on a real provider path is a visible redacted error and
    can never become a fabricated mock success.
12. pywebview starts with `private_mode=False` intentionally so the application
    profile can retain drafts and workspace state. A compatibility retry calls
    the older no-keyword signature only when the installed pywebview rejects
    that exact keyword.

## Consequences

- Browser fallback, native shells, and the add-on can share action and event
  semantics while choosing HTTP polling or direct event delivery.
- A web page from another origin cannot drive the local bridge through a
  normal browser fetch, even if it guesses the port. OS processes owned by the
  same user remain inside the local trust boundary; the token is CSRF/drive-by
  protection, not an operating-system sandbox.
- Provider/Anki cancellation may remain pending until the current finite
  network timeout expires. The UI nevertheless stops treating a cancelled
  operation as current, and late work cannot overwrite newer state.
- Developer tools that call the bridge directly must obtain or be passed the
  current process token instead of relying on an unauthenticated localhost
  endpoint.
