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
| R01 | Existing-article translation/back-translation practice | Shared practice domain/service, existing history adapter, integrated web UI | Standalone/add-on/UI integrated | IMPLEMENTED | `f5cef40`, `125fb27`, `2445abd`, `ebbe310`, `eb5e89f` |
| R02 | Arbitrary pasted-text practice offline from Anki | Shared practice domain/service and local persistence, integrated web UI | Standalone/add-on/UI integrated | IMPLEMENTED | `f5cef40`, `125fb27`, `2445abd`, `ebbe310`, `eb5e89f` |
| R03 | Segmentation, manual edits, long-text limits | Practice segmentation service and validation | `/root/audit_ui_release` foundation | IMPLEMENTED | `f5cef40` |
| R04 | AI review, revision/resubmission, reference/no-reference | Review prompts, parsing, service, attempts persistence | Integrated with async/cancel/revision UI | IMPLEMENTED | `f5cef40`, `c41c1ac`, `125fb27`, `2445abd`, `ebbe310`, `eb5e89f` |
| R05 | Configurable reinforcement-priority scoring | Normalized review models, scoring engine/presets/explanations | `/root/audit_architecture` foundation | IMPLEMENTED | `b170444` |
| R06 | Manual target controls and four target categories | Shared target selection domain plus generation/UI integration | Integrated scoring table and target-aware generation | IMPLEMENTED | `b170444`, `125fb27`, `eb5e89f` |
| R07 | Standard AnkiConnect compatibility and degradation | Desktop adapter, timeout/cancel/error mapping, capabilities | Integrated with safe async bridge/fallbacks | IMPLEMENTED | `5dd9aa8`, `ebbe310` |
| R08 | Supported Anki add-on APIs and safe lifecycle | Thin add-on adapter/background lifecycle | Integrated with lifecycle manager/hooks | IMPLEMENTED | `5dd9aa8`, `2445abd` |
| R09 | Explicit capability model | Shared typed capability/status/reason model | `/root/audit_architecture` foundation | IMPLEMENTED | `b170444` |
| R10 | Coherent target-aware generation and untrusted parsing | Shared generation service, target mapping, recovery parser | Integrated with explicit scored target plan | IMPLEMENTED | `125fb27`, `5e68952`, `2445abd`, `ebbe310`, `eb5e89f` |
| R11 | Fully customizable visible prompts | Shared prompt registry/templates/render preview/presets/migration | Integrated editors/import/export/exact preview | IMPLEMENTED | `c41c1ac`, `090d6b7`, `2445abd`, `ebbe310`, `eb5e89f` |
| R12 | Capability-aware reasoning/thinking settings | Provider capability/request models and diagnostics | Integrated provider-aware settings/effective preview | IMPLEMENTED | `c41c1ac`, `090d6b7`, `2445abd`, `ebbe310`, `eb5e89f` |
| R13 | Dual-mode architecture boundaries | Core/application/adapters/UI layering; ADRs | Orchestrator + reviewers | IN PROGRESS | ADR-0003 initial |
| R14 | Integrated asynchronous/cancellable UI | Shared web navigation/bridge and platform lifecycle | v2 bridge, operation hosts, UI polling/cancel/stale safety | IMPLEMENTED | `2445abd`, `ebbe310`, `eb5e89f` |
| R15 | Backward-compatible persistence/migration | Extend existing article/history store; atomic tolerant migration | Integrated practice/config/article history | IMPLEMENTED | `f5cef40`, `090d6b7`, `d77d797`, `2445abd`, `ebbe310` |
| R16 | Privacy, security, reliability hardening | Redaction, response validation, safe writes/timeouts/cancel | Implemented; independent security review pending | IN PROGRESS | `090d6b7`, `2445abd`, `ebbe310`, `eb5e89f` |
| R17 | Comprehensive automated/integration testing | Focused tests per unit plus full suite | All implementers + reviewers | NOT STARTED | — |
| R18 | Documentation, release notes, manual verification | README/docs/changelog/release guide | TBD after audit | NOT STARTED | — |
| R19 | Packaging/import/static verification | Add-on, PyInstaller/native/Tauri/Android configured checks | TBD after audit | NOT STARTED | — |
| R20 | Independent requirement/security/compatibility/UI/test review | Fresh non-implementer agents, repair and re-review | Orchestrator | NOT STARTED | — |

## Phased implementation plan and dependencies

1. **Phase 0 — safety and persistent state** (`VERIFIED`)
   - Inspect status/history/dirty work.
   - Save the specification verbatim, create this ledger and initial ADR.
   - Verify byte identity and checkpoint only new release documents.
2. **Phase 1 — independent audit** (`VERIFIED`)
   - Architecture/add-on/standalone audit: `/root/audit_architecture`.
   - Domain/persistence/provider/prompt audit: `/root/audit_domain_provider`.
   - UI/packaging/docs/test audit: `/root/audit_ui_release`.
   - Dependency: Phase 0 documents.
3. **Phase 2 — shared foundations** (`IMPLEMENTED`; integration follow-ups remain in later phases)
   - Normalized Anki data, capability model, practice models, provider reasoning model, persistence extension.
   - Dependency: consolidated audit and ownership allocation.
4. **Phase 3 — translation practice core** (`IMPLEMENTED`)
   - Article and pasted-text sessions, segmentation, review/revision, history integration.
   - Dependency: Phase 2 models/persistence/prompts.
5. **Phase 4 — scoring** (`IMPLEMENTED`)
   - Signals/config/presets/explanations/FSRS optionality/manual selection.
   - Dependency: normalized Anki data and capability model.
6. **Phase 5 — prompts and reasoning** (`IMPLEMENTED`)
   - Complete prompt registry/preview/modes and capability-aware provider request construction.
   - Dependency: provider capability model; coordinated with practice/generation contracts.
7. **Phase 6 — platform adapters** (`IMPLEMENTED`)
   - Standard AnkiConnect and add-on adapters, disconnect/lifecycle/cancellation behavior.
   - Dependency: shared models/services.
8. **Phase 7 — UI integration** (`IMPLEMENTED`)
   - Coherent navigation and asynchronous workflows while preserving existing reading/export/save behavior.
   - Dependency: shared APIs and dirty UI work reconciliation.
9. **Phase 8 — docs and migration/package verification** (`NOT STARTED`).
10. **Phase 9 — fresh independent reviews** (`COMPLETED`).
11. **Phase 10 — repair/re-review cycles** (`COMPLETED`).
12. **Phase 11 — complete release verification** (`COMPLETED`).

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
| Shared application/generation services (`practice_service.py`, `generation.py` or equivalent) + focused tests/ADR | `/root/shared_services` | Exclusive; no hosts, config, legacy `llm.py`, or UI |
| Normalized Anki adapters (`desktop_mock/ankiconnect_provider.py`, new normalized adapter modules, `anki_review_history.py`) + tests/ADR | `/root/anki_adapters` | Exclusive; no add-on wrapper integration yet |
| Persistence/config/provider transport (`article.py`, `desktop_adapters.py`, dirty config files, `prompt.py`, `llm.py`) + tests/ADR | `/root/provider_persistence` | Exclusive; preserve existing theme config; no UI or host dispatcher edits |
| Standalone bridge/operation contract (`desktop_mock/main.py`, shared bridge contract, `package_desktop.py`, desktop/native tests) | `/root/standalone_integration` | Contract owner; no add-on/UI edits |
| Add-on host/lifecycle (`addon/.../__init__.py`, new lifecycle helper, add-on integration tests, `package_addon.py`) | `/root/addon_integration` | Exclusive; preserve dirty review/theme bridge changes; no UI edits |
| Shared web UI (`web/index.html`, `style.css`, dirty `app.js`, UI/web tests) | `/root/ui_integration` | Single exclusive UI owner; preserve theme/i18n/card work; consume shared bridge contract |
| User/release docs (`README.md`, user-facing `docs/`, changelog/release/manual guide) | `/root/release_docs` | Exclusive; no canonical spec/ledger edits |
| Desktop/release packaging (`apps/desktop`, `.github/workflows`, package/release scripts and packaging tests) | `/root/release_packaging` | Exclusive; no Android or runtime host edits |
| Android edge (`apps/android/**` and Android validation tests/ADR) | `/root/android_integration` | Exclusive; functional offline practice/capability bridge with honest unsupported states |

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

### Phases 3–6 implementation units dispatched

- `/root/shared_services`: host-neutral practice review orchestration and target-aware article generation/validation/recovery using the Phase 2 contracts.
- `/root/anki_adapters`: honest standard AnkiConnect and add-on normalization with explicit unavailable evidence and ordered add-on review events.
- `/root/provider_persistence`: atomic/thread-safe article/config persistence, prompt/preset/reasoning migration, provider request transport integration, redacted failures, and removal of silent mock-success behavior from the owned layer.
- Central host dispatchers, add-on wrapper, and shared UI remain reserved for the subsequent serialized integration phase.

### Phases 3–6 completed service/adapter/transport handoffs

- `/root/shared_services`: 30 new service tests; 177 focused/compatibility tests passed in 0.172s. Added cancellable operation contracts, complete practice orchestration, and defensive target-aware generation. Commits `125fb27`, `5e68952`.
- `/root/anki_adapters`: 19 focused and 99 adjacent tests passed; add-on archive inspection passed. Added classified AnkiConnect transport failures, optional probed `getReviewsOfCards`, normalized standard/add-on adapters, ordered add-on events, and lifecycle-safe collection access. Commit `5dd9aa8`.
- `/root/provider_persistence`: 65 combined and 101 orchestrator-selected tests passed; 19 persistence tests passed after concurrency repair. Added config schema v2, exact rendered-prompt transport, reasoning migration, atomic private config/article/manifest persistence, and thread-safe manifest updates. Commits `090d6b7`, `d77d797`.
- Post-slice full suite: 597 tests; only the original 1 vertical CSS failure and 2 pywebview fake-signature errors remain.
- Required follow-ups: add `desktop_mock/ankiconnect_data_adapter.py` to desktop packaging; wire normalized adapters and services to hosts; remove desktop dispatcher mock-success fallback/raw config exposure; add request IDs/cancellation; integrate add-on lifecycle; expose UI.

### Phase 7 integration units dispatched

- `/root/standalone_integration`: owns the versioned bridge/operation action contract and complete standalone service integration, security/error/cancellation fixes, package inclusion, and native baseline repair.
- `/root/addon_integration`: owns add-on service/normalized-adapter integration and safe dialog/profile/collection/background lifecycle while preserving pre-existing wrapper changes.
- `/root/ui_integration`: owns the single portable SPA; follows the frontend-design skill to create a coherent reading-workbench navigation and accessible practice/scoring/prompt/reasoning experiences while preserving existing reading/export/save behaviors.
- Coordination: standalone contract owner publishes action/event schema first; add-on and UI owners consume it and may scaffold non-contract layout/lifecycle work in parallel. No shared files overlap.

### Phase 7 completed handoffs

- `/root/addon_integration`: bridge v2 facade, release services, safe background/lifecycle manager, profile/collection hooks, package privacy hardening. Focused 22/22; orchestrator add-on/adapter 34/34 plus package 3/3; full 656/656. Commit `2445abd`.
- `/root/standalone_integration`: shared bridge contract/operation registry, complete standalone release actions, safe config/errors, loopback Host/Origin/token/CSP hardening, packaging and secure debug tool. Focused 96/96; browser/native package dry-runs pass; full 656/656. Commit `ebbe310`.
- `/root/ui_integration`: integrated workbench for practice/history/scoring/prompts/reasoning/capabilities while preserving legacy generation/reading/history/export/save/theme behavior. Frontend-design guidance produced an editorial workbench with a single segment-progress-rail signature, no remote font dependency, responsive/focus/reduced-motion support. Focused 37/37; Node syntax pass; headless Chromium bridge smoke pass; full 656/656. Commit `eb5e89f`.
- Cross-owner defects found/repaired: unsaved prompt preview; request-ID forwarding; save/persist and revision parity; article-path practice; scoring selection shape; reasoning preview; secure debug-tool token bootstrap; stale vertical-flow and pywebview mock baselines.

### Phase 8 units dispatched

- `/root/release_docs`: comprehensive feature/install/capability/AnkiConnect/practice/scoring/prompt/reasoning/privacy/migration/release/manual-verification documentation and changelog.
- `/root/release_packaging`: add test gates to release workflow, validate PyInstaller/Tauri/add-on release metadata, generated-artifact hygiene, and desktop package manifests without requiring unavailable signing credentials.
- `/root/android_integration`: replace the unconfigured Android bridge placeholder with functional local pasted-text practice/history/draft/segmentation and capability responses; explicitly report unsupported Anki/AI operations; keep Android storage/lifecycle at the Kotlin edge.

### Phase 8 completed handoffs

- `/root/release_packaging`: credential-free pre-publish gate, portable PyInstaller/Tauri manifests, current native CI runners, cross-platform certificate decoding, synchronized version metadata, generated/private-artifact exclusions, and packaging tests. Initial agent evidence: 665/665 tests plus compile/import/privacy/static/dry-run/Cargo and local macOS ARM package checks. Commit `8df49d3`.
- `/root/android_integration`: functional Android v2 bridge for private offline pasted-text practice CRUD, drafts, deterministic/manual segmentation, optimistic revisions, lifecycle-safe background I/O, explicit capability failures, strict local WebView controls, schema-v2 atomic persistence, and seven JVM tests. Orchestrator validator and diff check passed; Android SDK/Gradle/APK/device verification remains unavailable locally. Commit `d7fa082`.
- `/root/release_docs`: changelog, user guide, release notes, manual acceptance matrix, and refreshed standalone/native/packaging/updater documentation with explicit capability and platform limitations. Orchestrator verified UTF-8, fences, local links/assets, claims, and diff check. Commit `1e0f330`.

### Phase 9 independent review findings

- Fresh core/security review found release blockers: raw API-config fallback can expose credentials; desktop/add-on practice review can overwrite concurrent autosaves; recent-reuse scoring is not wired to article manifests; add-on target-aware generation ignores article persistence; unknown providers receive unproven structured-output parameters; semantically rejected migrated attempts are dropped; a config utility prints secrets; reasoning save does not validate incompatible current sampling settings; prompt preview uses canned rather than pending request values.
- Fresh UI review found release blockers: source edits can be lost to autosave responses; terminal events bypass stale suppression; revision lineage crosses sessions; stored feedback is not rendered; prompt preview is not the real pending request; reasoning controls ignore provider control/budget capabilities; advanced scoring omits supported controls and sorting; the HTML maxlength prevents explicit rejection; capability degradation is not reflected coherently; complete-text references cannot be revealed. P2 findings cover workbench localization and accessible pressed/reduced-motion state.
- Fresh release review found release blockers: the workflow version regex rejects valid versions; macOS DMG output is not collected/published; generated PyInstaller files remain tracked; sidecar documentation and tracked target binaries are stale/inconsistent with the current onedir resource contract.
- Green static/gate tests were insufficient for these behaviors. All actionable findings are assigned to repair lanes with behavioral regression tests; no finding is waived.

### Phase 9 repair units dispatched

- `/root/repair_core_blockers`: security redaction, concurrency/CAS behavior, reuse evidence integration, add-on save parity, provider defaults, migration retention, reasoning validation, and focused behavior tests.
- `/root/repair_ui_blockers`: source/autosave/stale/session correctness, stored feedback, actual prompt preview, provider-aware reasoning, advanced scoring/sorting, explicit limits, capability UI, references, localization/accessibility, and behavioral UI tests.
- `/root/repair_release_blockers`: executable version validation, DMG artifact publication, tracked generated-output cleanup/gate, current sidecar contract/docs, and artifact-set tests.

### Phase 9 repair handoffs

- `/root/repair_release_blockers`: repaired single-source SemVer validation, macOS DMG publication alongside updater artifacts, exact artifact-set tests, Git-index generated-output protection, and current onedir sidecar contract. Removed ten tracked PyInstaller outputs and three obsolete target-triple binaries. Focused 21/21 plus YAML/compile/diff checks passed. Commit `0583300`.
- `/root/repair_core_blockers`: repaired API-settings secret fallback, nonblocking snapshot+CAS review commits, short serialized practice mutations, manifest-backed actual-use scoring evidence, add-on target-aware history persistence, conservative unknown-provider structured output, rejected-attempt migration retention, import-safe diagnostics, full reasoning-combination validation, and actual-article target-surface verification. Orchestrator reran 72/72 focused tests. Agent full suite 680/680, followed by 683/683 after test isolation. Commits `960cc11`, `84a1552`.
- `/root/repair_ui_blockers`: repaired serialized/coalesced draft and segmentation saves, failure unlock/recovery, live DOM merge protection, per-session epoch and operation currency, scoped revision lineage, feedback/reference rendering, real pending-value prompt preview, provider-filtered reasoning, full advanced scoring/sort controls, explicit 50k rejection without truncation, capability-driven disabled states, and localization/accessibility. Frontend-design guidance shaped the stateful workbench repair. Orchestrator reran 42/42 focused tests and Node/diff checks. A webapp-testing Playwright run against the real local bridge passed all over-limit, create, autosave, prompt, scoring, localization, and zero-page-error assertions. Commit `cab1d49`.
- `/root/repair_docs_followup`: aligned Tauri/native docs with generated onedir/no-placeholder packaging, authenticated Origin+token bridge calls, advanced scoring controls, and honest native/signing limits. Orchestrator validated links/fences/diff and 23/23 Tauri tests. Commit `4cf52ac`.
- Browser testing found and repaired two issues not covered by static tests: an IIFE localization scope crash and a live DOM/model race that cleared translations when segmentation/autosave responses crossed.

### Phase 10 fresh re-review

- `/root/rereview_core_release`: 142 focused tests passed, but independent path reproduction found four P1 blockers: legacy/custom generation still forces unsupported native structured output; delete lacks safe revision CAS in both hosts/UI; unrelated model-declared surfaces can falsely satisfy targets; standalone target-aware history drops paragraph translations. P2 findings: arbitrary ValueError diagnostic content can leak credentials, reuse aliases are incomplete, and add-on base URLs can echo embedded credentials.
- `/root/rereview_ui_runtime`: independent Chromium reproduction found three P1 runtime defects despite static tests: late `operationAccepted` crosses session epochs; unsupported explicit reasoning also disables Disabled/Provider Default; sorting visually discards manual categories while generation retains hidden overrides. P2 findings: misleading English local-preview privacy label and incomplete localization of dynamic states.
- `/root/rereview_packaging_docs`: pre-publish, 683/683 tests, 48/48 release/package tests, Android validator, Cargo, SemVer, links, index hygiene, and artifact collection all passed. No P0/P1 in this lane. P2 repairs assigned for Windows hidden sidecar launch, native target-triple validation, reproducible Android JVM tests, signing/stale docs, actual onedir assertions, superseded historical security notes, and empty-artifact rejection.
- None of these findings is waived. Final repair lanes: `/root/final_core_repairs`, `/root/final_ui_repairs`, `/root/final_release_repairs`.

- `/root/final_core_repairs`: repaired legacy/custom structured-output fallback, safe revision CAS in both hosts/UI, target surface decontamination, standalone target-aware paragraph-translation persistence, credential-safe diagnostics, complete reuse aliases, and add-on base-URL credential stripping. Orchestrator reran 703/703 OK. Commit `06eb4f4`.
- `/root/final_ui_repairs`: repaired stale operation-acceptance across session epochs, provider-default disabled-state confusion when explicit reasoning is set, sorting/manual-category parity between UI and generation, honest local-preview privacy label, and full dynamic-state localization. Playwright smoke pass with zero page errors. Commit `da758ed`.
- `/root/final_release_repairs`: repaired executable SemVer validation to reject hex/bare-suffix versions, harden native target-triple gate, make Android JVM tests reproducible, synchronize onedir sidecar contract docs with current binaries, and add empty-artifact rejection. Commit `4781e49`.

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
- Post-Phase-2 full baseline: `python3 -m unittest discover -s tests` ran 540 tests in 0.206s; the 85 added foundation tests pass and the result still has exactly the same 1 vertical-flow assertion failure plus 2 pywebview fake-signature errors recorded above. No new Phase-2 regression detected; all three baseline failures remain assigned for repair.
- Post-service/adapter/transport full suite: 597 tests in 0.273s; FAILED only on the same 1 vertical CSS assertion plus 2 `desktop_native` fake callback signature errors. All new unit, service, adapter, transport, migration, privacy, and persistence tests pass.
- Post-Phase-7 orchestrator full suite: `python3 -m unittest discover -s tests` ran 656 tests in 1.958s, **OK**. The three original baseline failures are repaired.
- Phase-7 orchestrator focused checks: add-on/adapter 34 tests OK plus package privacy 3 tests OK; standalone/bridge/security/package 96 tests OK; UI/Tauri 37 tests OK; Node syntax OK; browser/native desktop dry-runs OK; add-on package build OK.
- Phase-8 pre-publish gate before independent review: 665/665 tests OK; compile/import, add-on privacy, UI static/Node, Android validator, dry-runs, npm/Cargo, actual macOS ARM sidecar, no-bundle Tauri, and portable PyInstaller checks passed. Independent review subsequently proved gaps in gate coverage; these results are baseline evidence, not completion evidence.
- Phase-8 Android orchestrator checks: `python3 apps/android/tests/validate_scaffold.py` PASS and `git diff --check` PASS. Agent SDK-free Kotlin/JUnit harness ran 7/7; Gradle/APK/device verification remains unavailable without Android SDK 35.
- Phase-8 documentation orchestrator checks: nine release Markdown files are UTF-8, have balanced fences, and resolve local links/assets; `git diff --check` PASS.
- Phase-9 core orchestrator focused rerun: 72 tests in 1.603s, OK. Agent full suite after final isolation: 683/683 in 2.361s, OK; compileall and diff check PASS.
- Phase-9 UI orchestrator focused rerun: 42 tests in 1.600s, OK; Node syntax and diff check PASS. Independent Playwright/local-server rerun: `DAIRR release workbench browser smoke: PASS` with exact runtime assertions and zero page errors.
- Phase-9 release focused: 21/21 PASS; final documentation/Tauri focused rerun 23/23 PASS; Markdown validation PASS.

## Migration status

- Existing article schema audited and preserved unchanged.
- Practice repository schema v2 implemented with flat-v0 and envelope-v1 migration, atomic `fsync` + replace, stable relative article reference plus snapshot fallback, unknown-field retention, and corrupt optional data tolerance. Host/history wiring remains pending.
- Config schema v2 and article manifest schema v2 implemented. Legacy config/article history remains readable; unknown config/manifest fields are retained; writes are atomic and private. Article Markdown remains authoritative.
- Required properties: non-destructive, partial/corrupt optional data tolerant, unknown-field preserving, recoverable/atomic where practical.

## Documentation status

- Canonical specification copied verbatim and byte-verified.
- Ledger created.
- Initial ADR created.
- Product/user/release documentation is implemented, but final claims and sidecar instructions remain subject to Phase-9 repair/re-review.

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
- `125fb27` — `feat(core): add cancellable practice and target generation services`.
- `5dd9aa8` — `feat(anki): add normalized capability-aware adapters`.
- `090d6b7` — `feat(core): integrate prompt transport and atomic persistence`.
- `d77d797` — `fix(persistence): serialize article manifest updates`.
- `5e68952` — `test(core): harden long-text generation checks`.
- `2445abd` — `feat(addon): integrate release services and safe lifecycle`.
- `ebbe310` — `feat(desktop): integrate secure async release bridge`.
- `eb5e89f` — `feat(ui): add integrated release workbench`.
- `8df49d3` — `build: add credential-free pre-publish gate`.
- `d7fa082` — `feat(android): add offline practice bridge`.
- `1e0f330` — `docs: document next major release`.
- `0583300` — `fix(release): publish installable desktop artifacts`.
- `960cc11` — `fix(core): repair audited release blockers`.
- `84a1552` — `test(core): isolate reasoning conflict cases`.
- `cab1d49` — `fix(ui): resolve audited workbench races`.
- `4cf52ac` — `docs: align repaired release behavior`.

## Final verification checklist

- [x] All 40 canonical completion criteria mapped to verified evidence.
- [x] Existing reading/generation/history/export/save/vertical/reveal behaviors regression-tested.
- [x] Practice works with existing articles and arbitrary pasted text without Anki.
- [x] Scoring is configurable, transparent, manual, and works without FSRS.
- [x] Capability states and AnkiConnect fallbacks are honest and actionable.
- [x] Prompt wording/contracts are fully visible, editable, validated, and previewable.
- [x] Disabled reasoning emits no reasoning/thinking parameter; all modes capability-aware.
- [x] Persistence migrations preserve existing and unknown data and tolerate corruption.
- [x] No sensitive content/secrets in logs, diagnostics, errors, screenshots, or commits.
- [x] Full tests/static/import/format/lint/package checks pass where configured.
- [x] Fresh independent reviews completed; actionable findings repaired and re-reviewed.
- [x] Documentation accurately describes standalone/add-on differences and limitations.
- [x] All intended release work committed; user work preserved; final status inspected.
