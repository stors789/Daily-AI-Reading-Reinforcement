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
| R01 | Existing-article translation/back-translation practice | Shared practice domain/service, existing history adapter, integrated web UI | TBD after audit | NOT STARTED | — |
| R02 | Arbitrary pasted-text practice offline from Anki | Shared practice domain/service and local persistence, integrated web UI | TBD after audit | NOT STARTED | — |
| R03 | Segmentation, manual edits, long-text limits | Practice segmentation service and validation | TBD after audit | NOT STARTED | — |
| R04 | AI review, revision/resubmission, reference/no-reference | Review prompts, parsing, service, attempts persistence | TBD after audit | NOT STARTED | — |
| R05 | Configurable reinforcement-priority scoring | Normalized review models, scoring engine/presets/explanations | TBD after audit | NOT STARTED | — |
| R06 | Manual target controls and four target categories | Shared generation request/domain plus UI | TBD after audit | NOT STARTED | — |
| R07 | Standard AnkiConnect compatibility and degradation | Desktop adapter, timeout/cancel/error mapping, capabilities | TBD after audit | NOT STARTED | — |
| R08 | Supported Anki add-on APIs and safe lifecycle | Thin add-on adapter/background lifecycle | TBD after audit | NOT STARTED | — |
| R09 | Explicit capability model | Shared typed capability/status/reason model | TBD after audit | NOT STARTED | — |
| R10 | Coherent target-aware generation and untrusted parsing | Shared generation service, target mapping, recovery parser | TBD after audit | NOT STARTED | — |
| R11 | Fully customizable visible prompts | Shared prompt registry/templates/render preview/presets/migration | TBD after audit | NOT STARTED | — |
| R12 | Capability-aware reasoning/thinking settings | Provider capability/request models and diagnostics | TBD after audit | NOT STARTED | — |
| R13 | Dual-mode architecture boundaries | Core/application/adapters/UI layering; ADRs | Orchestrator + reviewers | IN PROGRESS | ADR-0003 initial |
| R14 | Integrated asynchronous/cancellable UI | Shared web navigation/bridge and platform lifecycle | TBD after audit | NOT STARTED | — |
| R15 | Backward-compatible persistence/migration | Extend existing article/history store; atomic tolerant migration | TBD after audit | NOT STARTED | — |
| R16 | Privacy, security, reliability hardening | Redaction, response validation, safe writes/timeouts/cancel | TBD after audit | NOT STARTED | — |
| R17 | Comprehensive automated/integration testing | Focused tests per unit plus full suite | All implementers + reviewers | NOT STARTED | — |
| R18 | Documentation, release notes, manual verification | README/docs/changelog/release guide | TBD after audit | NOT STARTED | — |
| R19 | Packaging/import/static verification | Add-on, PyInstaller/native/Tauri/Android configured checks | TBD after audit | NOT STARTED | — |
| R20 | Independent requirement/security/compatibility/UI/test review | Fresh non-implementer agents, repair and re-review | Orchestrator | NOT STARTED | — |

## Phased implementation plan and dependencies

1. **Phase 0 — safety and persistent state** (`IN PROGRESS`)
   - Inspect status/history/dirty work.
   - Save the specification verbatim, create this ledger and initial ADR.
   - Verify byte identity and checkpoint only new release documents.
2. **Phase 1 — independent audit** (`IN PROGRESS`)
   - Architecture/add-on/standalone audit: `/root/audit_architecture`.
   - Domain/persistence/provider/prompt audit: `/root/audit_domain_provider`.
   - UI/packaging/docs/test audit: `/root/audit_ui_release`.
   - Dependency: Phase 0 documents.
3. **Phase 2 — shared foundations** (`NOT STARTED`)
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
| Shared schemas/config/persistence/provider abstractions | TBD | One implementation owner at a time |
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

Implementation-agent reports must include: requirements addressed, assumptions, files changed, migrations, tests added, exact test results, unresolved issues, follow-ups, and commit hashes. Reports will be verified against repository state and diffs.

## Architecture decisions

- ADR-0003 (`docs/architecture/adr-0003-next-major-release-boundaries.md`): initial boundary and compatibility constraints; status Proposed pending Phase 1 audit.
- Further ADRs required after audit for persistence schema/migration, normalized Anki review data, prompt contracts, and provider reasoning semantics.

## Assumptions

- Existing article history is authoritative and must be extended rather than replaced.
- Shared logic belongs in `packages/dairr_core` when practical; bundled add-on core compatibility must remain operational until packaging confirms a safe consolidation mechanism.
- Standard AnkiConnect is the only standalone Anki integration baseline; enhanced data is optional and explicitly capability-gated.
- Pre-existing dirty work is user-owned until provenance is established; it may align with the release but will not be overwritten or committed accidentally.

## Tests and exact results

- No release tests run yet.
- Phase 0 byte-identity check: PASS. Source and canonical specification SHA-256 are both `14a8aa4cd094d9f8a194551e73d96dc7fa29b6c7d2d065f86285db5541d2a77d`.

## Migration status

- Existing schema not yet audited. No migration implemented.
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
- Phase 0 documentation checkpoint: pending.

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
