# Manual release verification guide

Use this checklist after automated tests pass and before calling a DAIRR build release-ready. Record the OS, architecture, Python/Anki/AnkiConnect versions, artifact hash, provider mode, commands, results, screenshots, and any private-data redactions. A check on one platform does not prove another platform.

## 1. Safety and clean-room preparation

- [ ] Work from a disposable Anki profile or a backed-up collection for write tests.
- [ ] Back up the standalone DAIRR app-data root and add-on `user_files`/config.
- [ ] Use a test API credential with limited scope/credit; never capture it in screenshots or logs.
- [ ] Prepare one legacy config, legacy Markdown article without a manifest, v0 practice record, v1 practice envelope, corrupt optional practice field, and current v2 record.
- [ ] Prepare text that is safe to send to the selected test provider. Do not use a real diary entry for release evidence.

## 2. Automated baseline

From the repository root, record exact output for the gates configured in the current checkout:

```bash
python3 -m unittest discover -s tests
python3 -m compileall .
python3 package_addon.py
python3 package_desktop.py --entry browser --dry-run
python3 package_desktop.py --entry native --dry-run
python3 package_tauri_sidecar.py --dry-run
python3 apps/android/tests/validate_scaffold.py
python3 scripts/desktop_release.py pre-publish
```

- [ ] No relevant test is skipped without a documented environmental reason.
- [ ] Packaging output contains no credentials, practice/history content, caches, or developer-local build data.
- [ ] Verify every produced archive/application from a clean extraction/install, not only the source checkout.
- [ ] Keep the exact `pre-publish` summary; a passing credential-free gate does not replace target-native signing/install/update tests.

## 3. Standalone macOS acceptance

- [ ] Build the sidecar and Tauri bundle on each supported Mac architecture.
- [ ] Verify a real sidecar replaced every placeholder.
- [ ] Launch the installed `.app` without a source checkout or system browser tab.
- [ ] Confirm the backend binds only to loopback and the window reaches the authenticated bridge.
- [ ] Quit and confirm the sidecar exits.
- [ ] Verify app config/articles/practice go to `~/Library/Application Support/DAIRR/` unless a legacy/explicit override is intentionally active.
- [ ] If distribution is claimed, verify Developer ID signature, notarization, stapling, Gatekeeper launch, updater signature, and update/install/restart. Otherwise label the artifact unsigned development-only.

## 4. Standalone Windows acceptance

- [ ] Build on Windows; do not treat a macOS dry-run as Windows evidence.
- [ ] Install into a clean Windows user account and launch from Start.
- [ ] Confirm WebView/runtime dependencies and bundled sidecar work without a repository checkout.
- [ ] Verify `%APPDATA%\DAIRR\` config/articles/practice and uninstall behavior.
- [ ] Confirm Windows Firewall does not expose the bridge beyond loopback.
- [ ] If distribution is claimed, verify Authenticode/timestamp, installer signature, SmartScreen behavior, updater signature, and update/install/restart. Otherwise label the artifact unsigned development-only.

## 5. AnkiConnect compatibility and failure matrix

With Anki running:

```bash
python3 desktop_app.py --provider ankiconnect --check
```

- [ ] Version, rated search, `cardsInfo`, article note-type checks pass.
- [ ] Deck/card loading works for the active profile.
- [ ] Lifetime `reps` is not shown as same-day attempt evidence in score explanations.
- [ ] Without authoritative day bounds, order-dependent signals are unavailable, not zero-valued “available”.
- [ ] FSRS retrievability/difficulty/stability are unavailable through standard `cardsInfo` and contribute zero.
- [ ] Optional `getReviewsOfCards` failure leaves other card evidence usable.
- [ ] `--check-write` creates one suspended test card only when intentionally run; delete it afterward.

Repeat UI checks for:

- [ ] Anki closed / connection refused.
- [ ] AnkiConnect disabled.
- [ ] Timeout or stalled endpoint.
- [ ] Malformed JSON.
- [ ] Incompatible version.
- [ ] Unsupported optional action.
- [ ] Missing/partial `cardsInfo` fields.
- [ ] Profile switch/stale connection.
- [ ] Cancellation.

Each case must produce actionable, redacted feedback while pasted practice remains usable.

## 5A. Android offline edge

- [ ] Re-run the seven SDK-free Android production-edge tests and `python3 apps/android/tests/validate_scaffold.py`; preserve their exact output.
- [ ] Run `gradle :app:testDebugUnitTest` and `gradle :app:assembleDebug` in a JDK 17/SDK 35 environment. These gates were not available in the current no-SDK environment.
- [ ] Install a debug/release candidate APK on a clean emulator/device; do not infer device behavior from static validation alone.
- [ ] Create multi-paragraph pasted practice offline, edit/split/merge/reorder segments, save, list, reopen, and delete it.
- [ ] Verify limits: source 50,000 characters, each segment 20,000, at most 500 segments, translation draft 100,000.
- [ ] Kill/recreate the Activity and process; saved session JSON recovers from app-private storage and unsaved translation recovery uses only local DOM storage.
- [ ] Confirm stale revisions, unsafe IDs, traversal, corrupt records, future schema, excessive input, and duplicate segment IDs fail with fixed messages that do not expose paths/text.
- [ ] Submit AI review and attempt article/Anki/scoring/prompt/reasoning actions; each fails closed with the documented capability message and the local draft remains.
- [ ] Attempt external navigation, `file:`/content access, mixed content, and post-destroy callbacks; the WebView/bridge rejects or safely discards them.
- [ ] Uninstall/clear storage only with disposable test data; application backup is disabled, no session export exists, and documentation must say either action deletes Android records.

## 6. Add-on lifecycle and compatibility

- [ ] Install the generated `.ankiaddon` into every documented Anki/PyQt6 target.
- [ ] Confirm **Tools → AI Reading Reinforcement** opens the shared workbench.
- [ ] Load current-day candidates and inspect ordered repeated grades from a controlled test card.
- [ ] Verify available supported FSRS fields independently; remove one and confirm only that signal becomes unavailable.
- [ ] Start a provider/Anki operation, then close the dialog; no callback touches a destroyed view.
- [ ] Repeat while closing the profile, unloading the collection, switching profiles, and quitting Anki.
- [ ] Confirm no collection, card, note, scheduler, dialog, window, or Qt object is retained across teardown.
- [ ] Confirm the add-on does not route its normal data access through AnkiConnect.

## 7. Practice acceptance

### Pasted text without Anki

- [ ] Close Anki completely.
- [ ] Open **Practice → Pasted text** and enter multi-paragraph safe test prose.
- [ ] Confirm source `auto`, explicit source, target language, direction, proficiency, and custom instructions persist.
- [ ] Verify 50,000 characters is accepted and 50,001 is rejected with no truncation.
- [ ] Split at cursor, merge next, reorder, and edit source segments before the first attempt.
- [ ] Switch between **One segment** and **Complete text** and confirm separate drafts.
- [ ] Reload/close-reopen and recover the latest local/saved draft.
- [ ] Save, find under **Practice history**, reopen, and delete.
- [ ] After first submission, confirm segmentation cannot silently change; a new session is required.

### Review behavior

- [ ] Submit a correct non-literal translation with no reference; feedback accepts valid alternatives.
- [ ] Test mistranslation, omission, unsupported addition, grammar, collocation, naturalness, register/tone, coherence, and proficiency mismatch.
- [ ] Confirm category feedback is concise/actionable and an improved translation is optional.
- [ ] Revise and resubmit; previous attempts remain visible and revision linkage is preserved.
- [ ] Cancel a review and confirm the draft/attempt is not lost.
- [ ] Force malformed, fenced, wrapped, partial, duplicated-field, plain-text, and truncated model responses; recover useful content or show a safe error without echoing raw private output.

### Article practice

- [ ] Create an article with paragraph `[T]` translations and save it.
- [ ] Open it from **DAIRR article** in source-to-target and back-translation directions.
- [ ] Confirm source/reference roles reverse correctly and **Reveal reference** is opt-in.
- [ ] Move/delete the original article and confirm the saved practice snapshot remains usable.
- [ ] Confirm the reference is a comparison point, not a verbatim grading key.

## 8. Scoring and target-plan acceptance

- [ ] Recommended reset produces stable defaults.
- [ ] Simple shows only designated controls; Advanced exposes all signals plus normalization divisor and optional contribution floor/ceiling fields.
- [ ] Toggle every signal and confirm disabled is distinct from unavailable.
- [ ] Test visible positive/negative weights and linear/sqrt/log1p/square transforms.
- [ ] Edit normalization divisors and optional contribution floor/ceiling fields directly; for recent reuse, enable decay and change the half-life. Save, reload, export, and re-import to confirm the visible values round-trip.
- [ ] Test None, Clamp 0–100, and candidate min–max normalization, including an equal-score set.
- [ ] Verify Again/Hard/Good/Easy, attempts, recovery, repeated failure, lapse, elapsed/overdue, state, FSRS, duplicate, sibling, and reuse contributions against controlled fixtures.
- [ ] Preview totals and inspect applied/disabled/unavailable evidence plus visible unavailability reasons.
- [ ] Adjust threshold, maximum, and Required/Preferred/Optional counts.
- [ ] Manually include below-threshold and exclude high-scoring cards.
- [ ] Exceed the automatic maximum with manual includes; choices remain present and the conflict is reported.
- [ ] Edit the final inclusion/category choices and choose **Use target plan**.
- [ ] Generate: required/preferred are prioritized, optional may be omitted, excluded use is warned, inflection/equivalents are accepted, and target mapping is preserved where structured output allows it.
- [ ] Import/export valid preset JSON; reject unknown signals, bad types/limits, non-finite values, and unsupported schema.

## 9. Prompt and reasoning acceptance

For all six prompt tasks:

- [ ] Replace both system and user wording completely and save at project/provider/profile scopes.
- [ ] Confirm profile > provider > project precedence.
- [ ] Inspect documented variables and render the exact final messages.
- [ ] Test multiline content, `{{literal braces}}`, missing variables, unknown variables, unmatched braces, and prohibited format/index/attribute syntax.
- [ ] Structured mode refuses a hidden/missing response contract and shows `{output_format_contract}` in preview.
- [ ] Plain-text mode sends no structured parsing requirement.
- [ ] Import/export/reset preserves valid overrides and unknown compatible extension fields.
- [ ] Confirm transport sends the rendered messages unchanged and appends no hidden substantive instruction.

For reasoning:

- [ ] Disabled emits no reasoning/thinking field.
- [ ] Provider default is stored distinctly and normally emits no override.
- [ ] OpenAI/OpenRouter expose only named efforts; Anthropic/Gemini expose only valid budgets.
- [ ] DeepSeek/Qwen/custom/unknown do not guess explicit support.
- [ ] Reject effort plus budget, unsupported effort, budget outside bounds, and advanced-body attempts to override managed fields.
- [ ] Verify temperature/top-p/response-format/streaming interactions for each known capability.
- [ ] Effective preview contains no API key, authorization, messages, private prompt, or private advanced value.

## 10. Reading/history regression

- [ ] Existing card-field selection and generation profiles still work.
- [ ] Horizontal and Japanese vertical reading render correctly.
- [ ] Paragraph translations reveal individually.
- [ ] Article activity/history filters and reopen work.
- [ ] Markdown/HTML export works.
- [ ] Save-to-card creates a suspended card and success/failure is visible.
- [ ] Exiting reading mode re-enables generation.
- [ ] Old Markdown without a manifest loads unchanged; new target-aware article has a safe adjacent manifest.

Use the existing visuals only for these preserved surfaces:

- `assets/dairr-workspace-cyber-violet.png`
- `assets/dairr-vertical-reading-cyber-violet.png`

Capture new release screenshots for Practice, Scoring Evidence, Prompt exact preview, API/Reasoning capability, and disconnected AnkiConnect only after visual checks pass. Use synthetic text and redact profile/deck/provider details.

## 11. Migration, crash, and privacy acceptance

- [ ] Load old config; preserve API profiles, credentials, legacy prompt preset, UI/theme, field config, and unknown fields while adding valid schema-v2 defaults.
- [ ] Corrupt one optional prompt/reasoning/scoring field; only that field falls back.
- [ ] Load v0/v1 practice records; save as v2 without losing unknown fields.
- [ ] Corrupt optional attempt/review/settings data; recover the usable session and preserve rejected optional data where designed.
- [ ] Reject future unsupported practice schema and path traversal/symlink escapes.
- [ ] Interrupt config/practice/article/manifest writes before replace; previous file remains intact and temp files are cleaned.
- [ ] Run concurrent article manifest updates; no update disappears.
- [ ] Search captured stdout/stderr, app logs, bridge errors, diagnostics, screenshots, generated package, and repository diff for API keys, pasted source, translations, private articles, full prompts, raw provider bodies, bridge tokens, and updater secrets.
- [ ] Verify loopback-only bind, exact Host/Origin policy, per-process bridge token, JSON/content-size enforcement, CSP, frame denial, no-referrer, MIME protection, and no-store.

## 12. Release evidence

- [ ] Record exact automated results and manual environments.
- [ ] Record every skipped/unavailable credentialed test as a limitation; do not convert it to “passed”.
- [ ] Attach artifact hashes and signature/notarization verification only after they succeed.
- [ ] Confirm docs describe the tested artifact and current Android capability state.
- [ ] Inspect `git status`; no intended release source is uncommitted and no generated/private artifact is staged.
- [ ] Independent reviewers have re-read the canonical specification, and all actionable findings are fixed or concretely justified.
