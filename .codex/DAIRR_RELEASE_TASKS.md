# DAIRR Next Major Release Task Ledger

Canonical specification: `docs/specs/next-major-release.md`

Status legend: `NOT STARTED`, `IN PROGRESS`, `BLOCKED`, `IMPLEMENTED`, `VERIFIED`.

## Repository safety baseline

- Branch: `main` tracking `origin/main`.
- Starting commit: `18be525` (`Merge pull request #1 from stors789/agent/anki-internal-provider-fix`).
- Pre-existing modified files, preserved and not owned by release agents until reconciled:
  - `addon/daily_ai_reading_reinforcement/__init__.py`
  - `addon/daily_ai_reading_reinforcement/config.json`
  - `addon/daily_ai_reading_reinforcement/web/app.js`
  - `packages/dairr_core/src/dairr_core/config.py`
  - `tests/test_web_i18n.py`
- Pre-existing untracked paths, preserved:
  - `addon/daily_ai_reading_reinforcement/anki_review_history.py`
  - `tests/test_anki_review_history.py`
  - `tests/test_web_card_interactions.py`
  - `config/`
  - `build/DAIRR/BUNDLE-00.toc`
  - `build/DAIRR/DAIRR`
- Policy: never reset, clean, overwrite, or silently incorporate unrelated user work. Production implementation ownership will be assigned after audits and dirty-diff reconciliation.

## Requirement-to-implementation matrix

| ID | Requirement group | Planned implementation surface | Owner | Status | Evidence/commit |
|---|---|---|---|---|---|
| R01 | Existing-article translation/back-translation practice | Shared practice domain/service, existing history adapter, integrated web UI | Practice foundation complete; integration owner TBD | IN PROGRESS | `f5cef40` |
| R02 | Arbitrary pasted-text practice offline from Anki | Shared practice domain/service and local persistence, integrated web UI | Practice foundation complete; integration owner TBD | IN PROGRESS | `f5cef40` |
| R03 | Segmentation, manual edits, long-text limits | Practice segmentation service and validation | `/root/audit_ui_release` foundation | IMPLEMENTED | `f5cef40` |
| R04 | AI review, revision/resubmission, reference/no-reference | Review prompts, parsing, service, attempts persistence | Prompt/review and practice foundations complete; pipeline integration TBD | IN PROGRESS | `f5cef40`, `c41c1ac` |
| R05 | Configurable reinforcement-priority scoring | Normalized review models, scoring engine/presets/explanations | `/root/audit_architecture` foundation | IMPLEMENTED | `b170444` |
| R06 | Manual target controls and four target categories | Shared target selection domain plus later generation/UI integration | `/root/audit_architecture` foundation | IN PROGRESS | `b170444` |
| R07 | Standard AnkiConnect compatibility and degradation | Desktop adapter, timeout/cancel/error mapping, capabilities | TBD after audit | NOT STARTED | — |
| R08 | Supported Anki add-on APIs and safe lifecycle | Thin add-on adapter/background lifecycle | TBD after audit | NOT STARTED | — |
| R09 | Explicit capability model | Shared typed capability/status/reason model | `/root/audit_architecture` foundation | IMPLEMENTED | `b170444` |
| R10 | Coherent target-aware generation and untrusted parsing | Shared generation service, target mapping, recovery parser | TBD after audit | NOT STARTED | — |
| R11 | Fully customizable visible prompts | Shared prompt registry/templates/render preview/presets/migration | Prompt foundation complete; config/UI integration TBD | IN PROGRESS | `c41c1ac` |
| R12 | Capability-aware reasoning/thinking settings | Provider capability/request models and diagnostics | Provider foundation complete; transport/config/UI integration TBD | IN PROGRESS | `c41c1ac` |
| R13 | Dual-mode architecture boundaries | Core/application/adapters/UI layering; ADRs | Orchestrator + reviewers | IN PROGRESS | ADR-0003 initial |
| R14 | Integrated asynchronous/cancellable UI | Shared web navigation/bridge and platform lifecycle | TBD after audit | NOT STARTED | — |
| R15 | Backward-compatible persistence/migration | Extend existing article/history store; atomic tolerant migration | Practice repository foundation complete; host/history integration TBD | IN PROGRESS | `f5cef40` |
| R16 | Privacy, security, reliability hardening | Redaction, response validation, safe writes/timeouts/cancel | TBD after audit | NOT STARTED | — |
| R17 | Comprehensive automated/integration testing | Focused tests per unit plus full suite | All implementers + reviewers | NOT STARTED | — |
| R18 | Documentation, release notes, manual verification | README/docs/changelog/release guide | TBD after audit | NOT STARTED | — |
| R19 | Packaging/import/static verification | Add-on, PyInstaller/native/Tauri/Android configured checks | TBD after audit | NOT STARTED | — |
| R20 | Independent requirement/security/compatibility/UI/test review | Fresh non-implementer agents, repair and re-review | Orchestrator | NOT STARTED | — |

## Phased implementation plan and dependencies

1. **Phase 0 — safety and persistent state** (`VERIFIED`)
   - Inspect status/history/dirty work.
   - Save the specification verbatim, create this ledger and initial ADR.
   - Verify byte identity and checkpoint only new release documents.
2. **Phase 1 — independent audit** (`IMPLEMENTED`; consolidation checkpoint pending)
   - Architecture/add-on/standalone audit: `/root/audit_architecture`.
   - Domain/persistence/provider/prompt audit: `/root/audit_domain_provider`.
   - UI/packaging/docs/test audit: `/root/audit_ui_release`.
   - Dependency: Phase 0 documents.
3. **Phase 2 — shared foundations** (`IMPLEMENTED`; integration follow-ups remain in later phases)
   - Normalized Anki data, capability model, practice models, provider reasoning model, persistence extension.
   - Dependency: consolidated audit and ownership allocation.
4. **Phase 3 — translation practice core** (`NOT STARTED`)
   - Article and pasted-text sessions, segmentation, review/revision, history integration.
   - Dependency: Phase 2 models/persistence/prompts.
5. **Phase 4 — scoring** (`NOT STARTED`)
   - Signals/config/presets/explanations/FSRS optionality/manual selection.
   - Dependency: normalized Anki data and capability model.
6. **Phase 5 — prompts and reasoning** (`NOT STARTED`)
   - Complete prompt registry/preview/modes and capability-aware provider request construction.
   - Dependency: provider capability model; coordinated with practice/generation contracts.
7. **Phase 6 — platform adapters** (`NOT STARTED`)
   - Standard AnkiConnect and add-on adapters, disconnect/lifecycle/cancellation behavior.
   - Dependency: shared models/services.
8. **Phase 7 — UI integration** (`NOT STARTED`)
   - Coherent navigation and asynchronous workflows while preserving existing reading/export/save behavior.
   - Dependency: shared APIs and dirty UI work reconciliation.
9. **Phase 8 — docs and migration/package verification** (`NOT STARTED`).
10. **Phase 9 — fresh independent reviews** (`NOT STARTED`).
11. **Phase 10 — repair/re-review cycles** (`NOT STARTED`).
12. **Phase 11 — complete release verification** (`NOT STARTED`).

## File and module ownership

| Surface | Owner | Concurrency rule |
|---|---|---|
| Canonical spec, ledger, cross-cutting ADRs | `/root` orchestrator | Orchestrator only |
| Repository audits | three named audit agents | Read-only |
| `capabilities.py`, `study_signals.py`, `scoring.py`, `target_selection.py` + focused tests/ADR | `/root/audit_architecture` | Exclusive; new files only; no config/host/UI edits |
| `practice.py`, `segmentation.py`, `practice_repository.py` + focused tests/ADR | `/root/audit_ui_release` | Exclusive; new files only; article history remains untouched in this unit |
| `prompt_templates.py`, `provider_capabilities.py`, `provider_requests.py`, `response_parsing.py`, `translation_review.py` + tests/ADR | `/root/audit_domain_provider` | Exclusive; new files only; no `prompt.py`, `llm.py`, or dirty config edits in this unit |
| Central web UI (`web/app.js`, `index.html`, `style.css`) | TBD after dirty-diff audit | Exclusive owner; no parallel edits |
| Add-on wrapper (`__init__.py`) | TBD after dirty-diff audit | Exclusive owner; preserve user changes |
| Desktop bridge/server/adapters | TBD | Exclusive by module group |
| Packaging metadata and release scripts | TBD | One release owner |
| Shared docs/README | TBD | One documentation owner after implementation |

## Subagent handoffs

### Audit agents dispatched

- `/root/audit_architecture`: read-only shared/desktop/add-on/capability/lifecycle architecture audit.
- `/root/audit_domain_provider`: read-only persistence/article/provider/prompt/config/privacy audit.
- `/root/audit_ui_release`: read-only UI/native/Tauri/Android/test/packaging/docs audit.

### Phase 1 verified findings

- Canonical shared logic is `packages/dairr_core/src/dairr_core`; add-on `core/` is a compatibility wrapper/vendor surface. New domain logic must not be implemented twice.
- Add-on and desktop dispatchers duplicate application behavior. A versioned host-neutral operation contract with request/operation IDs, safe public errors, cancellation, and stale-response handling is required before broad UI integration.
- Current review normalization is unsuitable for transparent scoring: standalone `review_count` is lifetime repetitions, rating searches lose order/multiplicity, dirty add-on grade aggregation also loses order/multiplicity, and both paths collapse sibling cards by note before scoring. Normalization must retain card and note identity and ordered events when actually available.
- Existing `learning_sources.py` types are useful but do not encode scheduling/FSRS signal availability or unavailability provenance.
- Existing article history is Markdown+HTML file storage with no schema version. It must remain authoritative. Practice data should be an adjacent versioned JSON repository using stable IDs, relative article references plus snapshot fallback, atomic replacement, unknown-field preservation, and corrupt-optional-data tolerance.
- Desktop history currently mutates global `ARTICLES_DIR` in a threaded server; configuration and article writes are non-atomic. These require repair during persistence integration.
- Current LLM path is a direct chat-completions call with a fixed hidden system prompt, brittle response assumptions, raw provider-error propagation, no cancellation, no provider capabilities, and no reasoning model. Prompt rendering uses `str.format` without a variable registry or complete preview.
- Desktop `getConfig` exposes raw keys. Generic bridge/provider errors can expose raw provider bodies. Real generation failure silently falls back to a mock success. These are release-blocking privacy/correctness issues.
- Shared web UI is a monolithic SPA. One owner must exclusively integrate navigation and the practice/scoring/prompt/reasoning workspaces while preserving vertical reading, paragraph reveal, export, history, and save-to-card.
- Add-on background callbacks retain dialog/web/collection references without full close/profile/unload guards. Desktop operations lack cancellation and response ordering. Android is currently an unconfigured fail-closed scaffold, not a functional parity implementation.
- Tauri process startup/shutdown is relatively robust, but checked-in sidecars are placeholders; signed cross-platform verification requires unavailable platform credentials/environments and must be reported honestly.
- Root `build/` has tracked/untracked PyInstaller products and is not ignored. Generated output must never be staged accidentally; pre-existing artifacts remain untouched pending a scoped hygiene decision.

### Phase 1 risks by priority

- **P0:** silent mock fallback after real generation failure; raw config/key exposure; unsafe add-on lifecycle for new long operations.
- **P1:** fabricated/ambiguous scoring semantics; no capability provenance; non-atomic/thread-unsafe persistence; provider error leakage; no cancellation/request ordering; localhost bridge threat model.
- **P2:** monolithic duplicated host/application logic; Android parity strategy unresolved; no configured lint/type/format gate.

Implementation-agent reports must include: requirements addressed, assumptions, files changed, migrations, tests added, exact test results, unresolved issues, follow-ups, and commit hashes. Reports will be verified against repository state and diffs.

### Phase 2 implementation units dispatched

- Shared capability/study-signal/scoring/target-selection foundations: `/root/audit_architecture`.
- Practice domain/segmentation/versioned atomic repository foundations: `/root/audit_ui_release`.
- Prompt registry/provider capability/request/review-parsing foundations: `/root/audit_domain_provider`.
- Agents edit disjoint new files and run focused tests in parallel, but do not stage or commit concurrently. The orchestrator will serialize commit handoffs to avoid the shared Git index race.

### Phase 2 completed handoffs

- `/root/audit_ui_release` implemented the practice domain, segmentation, and v2 atomic practice repository. Agent report: 15 new tests; 18 focused/core tests passed. Orchestrator independently reran 18 tests in 0.026s, all passed; compile check passed. Commit: `f5cef40`.
- `/root/audit_architecture` implemented capability/study-signal models, configurable scoring, explanations, preset serialization, and target selection. Agent report: 30 new tests; 38 focused/core tests passed. Orchestrator independently reran 38 tests in 0.029s, all passed; compile and forbidden-import scan passed. Commit: `b170444`.
- `/root/audit_domain_provider` implemented complete prompt registry/rendering, provider reasoning capabilities/request construction, tolerant response parsing, and translation-review parsing. Orchestrator independently ran 43 focused/core tests in 0.025s, all passed; compile and forbidden-import/sensitive-pattern scan passed. Commit: `c41c1ac`.
- Integration review follow-ups: decide whether practice autosave should avoid mutating the passed session; preserve shape-valid but semantically rejected attempts; wire prompt/preset migration into config; ensure preview content is never used as default diagnostics; map legacy rating sets to unavailable ordered evidence rather than fabricated events.

## Architecture decisions

- ADR-0003 (`docs/architecture/adr-0003-next-major-release-boundaries.md`): initial boundary and compatibility constraints; status Proposed pending Phase 1 audit.
- Further ADRs required for normalized Anki/capability semantics; persistence schema/migration; async operation protocol; prompt/provider reasoning contracts; targets/generation parsing; Android scope; and localhost bridge security.
- ADR-0004 records normalized signal, availability, heuristic scoring, and target-selection semantics.
- `docs/architecture/adr-practice-persistence.md` records the adjacent v2 JSON practice repository and non-destructive migration strategy.
- ADR-0006 records fully visible prompt contracts and provider-specific reasoning omission/mapping rules.

## Assumptions

- Existing article history is authoritative and must be extended rather than replaced.
- Shared logic belongs in `packages/dairr_core` when practical; bundled add-on core compatibility must remain operational until packaging confirms a safe consolidation mechanism.
- Standard AnkiConnect is the only standalone Anki integration baseline; enhanced data is optional and explicitly capability-gated.
- Pre-existing dirty work is user-owned until provenance is established; it may align with the release but will not be overwritten or committed accidentally.

## Tests and exact results

- Phase 0 byte-identity check: PASS. Source and canonical specification SHA-256 are both `14a8aa4cd094d9f8a194551e73d96dc7fa29b6c7d2d065f86285db5541d2a77d`.
- Phase 1 agents were explicitly read-only; no tests run by audit agents. Architecture audit reports `git diff --check` PASS at audit time.
- Pre-integration baseline on the preserved dirty tree: `python3 -m unittest discover -s tests` ran 455 tests in 0.189s, result **FAILED** (1 failure, 2 errors):
  - `test_desktop_native.TestDesktopNativeCli.test_provider_and_ankiconnect_url_are_written_to_environment` ERROR: test fake does not accept the current `private_mode=False` keyword.
  - `test_desktop_native.TestDesktopNativeCli.test_pywebview_present_creates_window_and_starts` ERROR: same fake signature mismatch.
  - `test_tauri_app_shell.TauriAppShellTests.test_vertical_translation_is_overlay_and_does_not_reflow_article` FAIL: preserved dirty CSS currently uses static flow while the test expects absolute overlay positioning.
  - These failures predate Phase 2 implementation and must be reconciled by an exclusive integration/repair owner; they are not accepted release limitations.
- Practice foundation independent verification: 18 tests in 0.026s, OK; compile OK.
- Scoring/capability/target independent verification: 38 tests in 0.029s, OK; compile/import scans OK.
- Prompt/provider/review independent verification: 43 tests in 0.025s, OK; compile/import/sensitive-pattern scans OK.

## Migration status

- Existing article schema audited and preserved unchanged.
- Practice repository schema v2 implemented with flat-v0 and envelope-v1 migration, atomic `fsync` + replace, stable relative article reference plus snapshot fallback, unknown-field retention, and corrupt optional data tolerance. Host/history wiring remains pending.
- Required properties: non-destructive, partial/corrupt optional data tolerant, unknown-field preserving, recoverable/atomic where practical.

## Documentation status

- Canonical specification copied verbatim and byte-verified.
- Ledger created.
- Initial ADR created.
- Product/user/release documentation: not started.

## Known limitations and unresolved defects

- Pre-existing dirty working tree prevents an unconditional whole-tree checkpoint commit; only explicitly scoped release-document files may be committed.
- `.codex` was initially blocked by the managed filesystem profile; scoped approval was obtained to create the required repository-local directory.
- No implementation or release-blocker conclusions until Phase 1 audits complete.

## Relevant commits

- Starting baseline: `18be525`.
- `6585f38` — `docs: add major release specification` (canonical spec, initial ledger, ADR-0003).
- `0370a10` — `docs: record release architecture audit`.
- `f5cef40` — `feat(practice): add translation session persistence`.
- `b170444` — `feat(scoring): add configurable reinforcement priority`.
- `c41c1ac` — `feat(prompts): add customizable provider-aware workflows`.

## Final verification checklist

- [ ] All 40 canonical completion criteria mapped to verified evidence.
- [ ] Existing reading/generation/history/export/save/vertical/reveal behaviors regression-tested.
- [ ] Practice works with existing articles and arbitrary pasted text without Anki.
- [ ] Scoring is configurable, transparent, manual, and works without FSRS.
- [ ] Capability states and AnkiConnect fallbacks are honest and actionable.
- [ ] Prompt wording/contracts are fully visible, editable, validated, and previewable.
- [ ] Disabled reasoning emits no reasoning/thinking parameter; all modes capability-aware.
- [ ] Persistence migrations preserve existing and unknown data and tolerate corruption.
- [ ] No sensitive content/secrets in logs, diagnostics, errors, screenshots, or commits.
- [ ] Full tests/static/import/format/lint/package checks pass where configured.
- [ ] Fresh independent reviews completed; actionable findings repaired and re-reviewed.
- [ ] Documentation accurately describes standalone/add-on differences and limitations.
- [ ] All intended release work committed; user work preserved; final status inspected.
