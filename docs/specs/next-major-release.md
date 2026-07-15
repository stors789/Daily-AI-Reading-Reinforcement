Implement the next major DAIRR release end-to-end and leave the repository in a genuinely release-ready state.
Work autonomously. I will not be available to answer questions or approve intermediate decisions. Do not stop to ask for clarification, confirmation, permission, or manual intervention unless proceeding would risk irreversible data loss, expose secrets, or require credentials that are genuinely unavailable.
When a requirement is underspecified, inspect the existing product and architecture, choose the most backward-compatible and maintainable interpretation, document the decision, and continue.
Do not stop after planning, scaffolding, partial implementation, or a single test pass. Continue through implementation, integration, testing, review, defect fixing, documentation, packaging checks, and final verification.
Project context
DAIRR is a dual-mode project:
1. a standalone desktop application;
2. an Anki add-on.
The two modes should share as much domain and application logic as practical, but their Anki integration capabilities differ:
- the Anki add-on may use supported Anki internal APIs;
- the standalone desktop application must communicate with Anki through standard AnkiConnect and must not assume access to Anki’s internal Python objects.
Preserve feature parity wherever the underlying platform permits it. Where parity is impossible, expose capability differences honestly and degrade gracefully.
The project already has an article-history and persistence system. Do not replace or independently reimplement it. Inspect it, preserve existing data, and extend it only where required.
Mandatory agent orchestration model
The main agent must act as an orchestrator, integrator, and reviewer rather than as the primary implementer.
The main agent may:
- inspect enough repository context to understand the architecture;
- create the canonical specification and task ledger;
- divide work into coherent phases;
- assign work to specialized subagents;
- coordinate dependencies and file ownership;
- inspect plans, diffs, commits, test results, and requirement coverage;
- integrate subagent branches or worktrees;
- dispatch review and repair subagents;
- produce the final consolidated report.
The main agent must not perform the substantive production implementation itself.
Delegate substantive work to subagents, including:
- repository and architecture investigation;
- feature implementation;
- production-file editing;
- tests;
- migrations;
- documentation;
- security review;
- compatibility review;
- UI review;
- final requirement audit;
- defect repair.
Use parallel subagents where tasks are genuinely independent.
Do not allow multiple subagents to modify overlapping files concurrently unless they use isolated worktrees or branches and there is an explicit integration plan.
Assign clear ownership for shared files such as:
- configuration schemas;
- persistence models;
- provider abstractions;
- central UI navigation;
- packaging metadata;
- shared documentation.
Every implementation subagent must report:
- requirements addressed;
- architectural assumptions;
- files changed;
- migrations added;
- tests added;
- tests executed and exact results;
- unresolved issues;
- follow-up work required;
- commit hashes created.
The main agent must verify these reports against the actual repository rather than trusting summaries blindly.
Persistent specification and context management
The default model context may be compacted during this task. Do not rely on conversational memory as the authoritative source of requirements or progress.
Before substantive implementation:
1. Save this complete request verbatim as:
   docs/specs/next-major-release.md
2. Treat that file as the canonical product specification.
3. Create:
   .codex/DAIRR_RELEASE_TASKS.md
4. The task ledger must contain at least:
   - requirement-to-implementation matrix;
   - phased implementation plan;
   - dependencies;
   - assigned subagents;
   - file or module ownership;
   - status of every requirement;
   - relevant commits;
   - tests and exact results;
   - architecture decisions;
   - assumptions;
   - known limitations;
   - unresolved defects;
   - migration status;
   - documentation status;
   - final verification checklist.
5. Create an architecture decision record or equivalent persistent document for important decisions that affect compatibility, persistence, provider behavior, or the standalone/add-on boundary.
6. Update the task ledger after every substantial implementation unit, subagent handoff, review, repair cycle, and phase transition.
7. After any context compaction, handoff, interruption, or substantial phase transition, reread:
   - docs/specs/next-major-release.md;
   - .codex/DAIRR_RELEASE_TASKS.md;
   - relevant architecture decisions;
   - the latest applicable commits.
8. Do not use a subagent summary as the sole record of a requirement or architectural decision.
9. Before declaring completion, launch fresh review subagents that independently reread the canonical specification.
Git safety and frequent commits
Commit work frequently in small, coherent, reviewable units.
Git requirements:
- Inspect repository status and current branch before making changes.
- Preserve all pre-existing uncommitted user work.
- Never discard, overwrite, reset, clean, or revert unrelated user changes.
- Do not use destructive commands such as git reset --hard, destructive checkout, or forced cleanup.
- Do not force-push.
- Do not rewrite existing history unless repository policy explicitly requires it.
- Do not commit API keys, credentials, private user text, generated personal content, local databases, logs containing sensitive content, build artifacts, caches, virtual environments, or unrelated files.
- Respect the existing .gitignore; improve it if necessary.
- Use an isolated branch or worktree when appropriate and supported by the environment.
- Make a checkpoint commit before risky migrations or broad architectural refactors.
- Commit after each coherent implementation unit rather than accumulating one enormous diff.
- Commit tests with the implementation they verify when practical.
- Commit documentation and migration notes alongside the relevant feature.
- Do not make meaningless commits after every tiny edit.
Aim for commits corresponding to units such as:
- canonical specification and task ledger;
- normalized Anki data-access interfaces;
- translation-practice domain model;
- pasted-text practice core;
- AI translation-review pipeline;
- configurable scoring engine;
- scoring UI and explanation model;
- customizable prompt infrastructure;
- reasoning capability infrastructure;
- standalone integration;
- add-on integration;
- persistence migration;
- tests for each subsystem;
- documentation;
- fixes from independent review;
- final release verification.
Use clear commit messages, preferably following the repository’s existing convention. If none exists, use concise conventional-style messages such as:
- docs: add major release specification
- feat(practice): add pasted-text translation sessions
- feat(scoring): add configurable reinforcement priority
- feat(prompts): support fully custom templates
- feat(providers): add capability-aware reasoning settings
- fix(ankiconnect): degrade gracefully on missing review data
- test(persistence): cover practice-session migrations
- docs: document dual-mode feature differences
Record relevant commit hashes in .codex/DAIRR_RELEASE_TASKS.md.
After every major phase:
- ensure the work is committed;
- run the relevant focused tests;
- update the task ledger;
- inspect the resulting diff and repository status;
- continue automatically.
Do not stop merely because a commit was created.
Existing functionality that must be preserved
Preserve all currently working functionality, including:
- selecting decks and card fields;
- collecting cards studied during the current Anki day;
- generating reading passages from selected card content;
- browsing previously generated articles;
- paragraph-by-paragraph translation reveal;
- Japanese vertical reading mode;
- article export;
- saving articles back to Anki as suspended reading cards;
- OpenAI-compatible API providers;
- standalone desktop operation;
- Anki add-on operation;
- existing configuration and persistence behavior unless explicitly migrated.
Do not replace working architecture merely because rewriting is easier.
1. Flexible translation and back-translation practice
Implement a general translation-practice workspace that is not restricted to articles generated by DAIRR.
Support at least two entry paths.
1A. Practice from an existing DAIRR article
Allow users to select a previously generated article from the existing article-history system.
Support configurable translation direction.
Depending on the direction, users should be able to:
- hide the original target-language text;
- view the source-language text or existing translation;
- write their own target-language translation;
- practise paragraph by paragraph;
- practise the complete article;
- reveal the original reference paragraph when one exists;
- submit their translation for AI review;
- revise and resubmit;
- view previous attempts and feedback where stored.
Do not require verbatim reconstruction.
When an existing target-language reference is present, use it as an additional comparison point rather than treating it as the only acceptable answer.
1B. Practice from arbitrary pasted text
Allow users to paste any source-language prose directly into the application.
The text may be:
- a diary entry;
- personal notes;
- a news article;
- an essay;
- a social-media post;
- a story;
- study material;
- copied prose;
- any other user-provided text.
Do not assume that pasted text:
- was generated by DAIRR;
- exists in Anki;
- has an official translation;
- has vocabulary metadata;
- is publicly available.
Users must be able to:
- paste or edit source text;
- select or detect the source language;
- choose the target language;
- optionally choose a proficiency level;
- provide custom review instructions;
- divide the text into paragraphs or logical segments;
- manually adjust segmentation;
- translate one segment at a time;
- translate the entire text;
- submit translations for AI review;
- revise and resubmit;
- preserve unsaved work safely;
- optionally save the session into the existing history system;
- reopen saved sessions later.
The pasted-text practice workspace must remain usable when:
- Anki is closed;
- AnkiConnect is missing;
- AnkiConnect is unreachable;
- no deck is configured;
- no FSRS data is available.
Handle longer texts through clear segmentation, context management, and explicit limits. Do not fail silently or truncate user text without warning.
1C. AI review behavior
The AI reviewer should evaluate:
- preservation of meaning;
- mistranslations;
- omissions;
- unsupported additions;
- grammar;
- vocabulary choice;
- collocations;
- idiomaticity;
- naturalness;
- register;
- tone;
- coherence;
- stylistic similarity when a reference exists;
- appropriateness for the selected proficiency level.
The reviewer must:
- distinguish genuine errors from acceptable alternatives;
- avoid demanding literal or verbatim reproduction;
- explain important meaning errors clearly;
- identify wording that is grammatically correct but unnatural;
- avoid overcorrecting valid stylistic variation;
- provide concise and actionable feedback;
- optionally provide an improved translation;
- support paragraph-level review;
- support complete-text review;
- adapt to user-provided review instructions;
- avoid inventing a canonical answer when no reference translation exists.
When no target-language reference exists, evaluate the user translation directly against the source text.
Where practical, structure the result into categories such as:
- meaning;
- omissions and additions;
- grammar;
- vocabulary;
- naturalness;
- register and style;
- suggested revision.
Do not expose pasted text, user translations, or feedback in logs.
2. Configurable reinforcement-priority scoring
Improve the selection and ranking of reviewed cards so DAIRR does not force too many easy, low-value, duplicated, recently reused, or weakly useful targets into one generated article.
Use current Anki-day review history and, when available, FSRS-related data to calculate a reinforcement-priority score.
Potential signals include:
- Again responses;
- Hard responses;
- Good responses;
- Easy responses;
- repeated reviews during the same Anki day;
- number of same-day attempts;
- initial failure followed by later recovery;
- repeated same-day failure;
- recent lapses;
- historical lapse count;
- current retrievability;
- FSRS difficulty;
- FSRS stability;
- elapsed time;
- overdue status;
- card state;
- whether a card is new, learning, relearning, or review;
- note duplication;
- sibling cards;
- repeated or equivalent target expressions;
- recent inclusion in generated articles;
- time since last use in a DAIRR article.
Do not present the result as a scientifically perfect measure of intrinsic card difficulty.
Present it as a transparent and configurable reinforcement-priority heuristic.
2A. User-configurable scoring mechanism
Users must be able to configure the scoring mechanism rather than being forced to use one fixed formula.
For each major signal, provide where appropriate:
- enable or disable toggle;
- adjustable weight;
- sensible default;
- explanation;
- input validation;
- minimum and maximum contribution;
- optional nonlinear transformation;
- optional decay behavior;
- normalization behavior.
Support settings such as:
- duplicate penalties;
- sibling-card penalties;
- recent-reuse penalties;
- same-day-failure bonuses;
- recovery-after-failure handling;
- score normalization;
- minimum inclusion score;
- maximum selected-card count;
- required target count;
- preferred target count;
- optional target count.
Provide:
- a recommended default preset;
- a simple mode;
- an advanced mode;
- reset-to-default;
- preset import and export when compatible with the existing configuration architecture.
The simple mode should expose only the most useful controls.
The advanced mode should expose per-signal toggles, weights, and transformations.
2B. Score transparency and manual control
Allow users to:
- preview all candidate cards;
- view each card’s total score;
- inspect a contribution breakdown;
- see which signals were available;
- see which signals were unavailable;
- understand why a card ranked highly or poorly;
- sort by priority;
- choose a score threshold;
- limit the selected-card count;
- manually include cards;
- manually exclude cards;
- edit the final target list;
- classify targets as required, preferred, optional, or excluded.
The explanation system must not imply unavailable data was present.
2C. FSRS availability
The scoring system must work when FSRS information is absent.
FSRS-dependent signals must:
- disable themselves gracefully;
- be clearly marked as unavailable;
- contribute nothing rather than a fabricated neutral value;
- not make the rest of the scoring system unusable.
2D. Shared scoring engine and normalized data
Keep scoring logic independent from platform-specific Anki data access.
Create a normalized domain representation for card, review, and scheduling signals.
Both integrations should feed normalized data into the same scoring engine:
- Anki add-on adapter;
- standalone AnkiConnect adapter.
Do not duplicate scoring formulas between the two modes.
3. Standalone AnkiConnect compatibility
The standalone desktop application must communicate with Anki only through standard AnkiConnect.
Audit which required fields and review-history information are available through standard AnkiConnect actions.
Do not assume access to:
- Anki’s Python collection object;
- scheduler internals;
- Qt objects owned by Anki;
- add-on hooks;
- internal database handles.
Where standard AnkiConnect cannot provide a scoring signal:
- degrade gracefully;
- mark the signal unavailable;
- do not invent data;
- do not disable the entire scoring system;
- preserve all scoring signals that remain available;
- document the limitation.
If an optional custom AnkiConnect extension would improve functionality:
- keep it optional;
- isolate it from the standard compatibility path;
- do not require it for core standalone operation;
- document installation and fallback behavior.
The standalone application must handle:
- Anki not running;
- AnkiConnect not installed;
- connection refusal;
- timeout;
- malformed JSON;
- incompatible action versions;
- unsupported actions;
- partial responses;
- missing fields;
- stale connections;
- cancellation.
Display actionable setup and troubleshooting guidance.
Do not freeze the desktop UI while waiting for AnkiConnect.
Pasted-text translation practice must work even when Anki integration is completely unavailable.
4. Anki add-on compatibility
The add-on may use supported Anki APIs.
It must:
- avoid blocking Anki’s main UI;
- handle profile closure safely;
- handle collection unload safely;
- handle dialog and window destruction safely;
- avoid retaining invalid collection references;
- avoid retaining invalid Qt object references;
- cancel or detach background work appropriately;
- use supported hooks and APIs;
- remain compatible with the project’s documented Anki and PyQt6 versions;
- integrate naturally into existing menus and windows.
Do not use AnkiConnect from the add-on when a supported internal API is more appropriate.
5. Explicit capability model
Create an explicit capability model rather than scattering mode checks throughout the code.
Represent capabilities such as:
- Anki connection available;
- internal Anki APIs available;
- review history available;
- FSRS values available;
- article history available;
- pasted-text practice available;
- target-card scoring available;
- custom prompt support available;
- provider reasoning control available;
- cancellation available.
The UI should distinguish:
- available;
- temporarily unavailable;
- unavailable in standalone mode;
- unavailable because Anki is disconnected;
- unavailable because FSRS data is absent;
- unavailable because the selected provider lacks support;
- dependent on an optional extension.
6. Article generation quality and target handling
Improve article generation so selected vocabulary is treated as learning material rather than as strings that must be inserted mechanically.
Support target categories:
- required;
- preferred;
- optional;
- excluded.
The generation system should:
- prioritize coherence;
- prioritize natural language;
- allow grammatical inflection;
- allow necessary morphological transformation;
- recognize reasonable equivalent surface forms;
- avoid unnatural repetition;
- avoid implausible stories created only to fit vocabulary;
- respect language;
- respect proficiency;
- respect genre;
- respect desired length;
- respect style;
- respect custom instructions;
- report targets that could not be used naturally;
- preserve a machine-readable mapping between targets and actual usage where practical.
Do not force every optional target into the output.
Add robust handling for:
- malformed structured responses;
- partially valid responses;
- missing fields;
- duplicated fields;
- unexpected target mappings;
- plain-text responses;
- provider-added wrappers;
- truncated output.
Treat all model output as untrusted input.
Where structured parsing fails, attempt safe recovery and provide a useful error rather than crashing.
7. Fully customizable prompts
Implement a complete prompt-customization system.
Users must be able to inspect and customize the actual prompts used for major AI operations, including at least:
- article generation;
- translation review;
- back-translation review;
- target-usage validation;
- text segmentation;
- preprocessing where model-powered;
- any new model-powered workflow introduced by this release.
Support:
- editable system prompts;
- editable user-prompt templates;
- documented variables;
- prompt preview;
- final rendered prompt preview before submission;
- reset to project defaults;
- per-task settings;
- optional provider-specific overrides;
- optional profile-specific overrides;
- preset import and export;
- multiline editing;
- safe brace handling;
- escaping;
- validation;
- backward-compatible migration.
Document variables such as:
- source text;
- source language;
- target language;
- proficiency level;
- selected vocabulary;
- required targets;
- preferred targets;
- optional targets;
- excluded targets;
- user translation;
- reference translation;
- article genre;
- desired length;
- custom instructions;
- segmentation instructions;
- output-format contract.
Users must be able to replace project-provided wording completely.
Do not silently append substantial hidden instructions to a supposedly fully custom prompt.
Any mandatory technical wrapper, output schema, or parser contract must be:
- visible;
- documented;
- represented in prompt preview.
Support at least two operating styles where practical:
1. structured-output mode with an explicit visible response contract;
2. plain-text mode that does not require structured parsing.
Validate missing required variables before sending a request.
Do not silently repair a custom prompt in a way that changes its intended meaning.
8. API reasoning and thinking settings
Extend OpenAI-compatible API settings with optional reasoning or thinking controls.
The setting must distinguish at least:
- disabled;
- provider default;
- explicit provider-supported level.
When disabled:
- omit reasoning and thinking parameters entirely;
- do not substitute a minimal level.
When provider default is selected:
- omit explicit overrides unless the provider API specifically requires a default marker.
Potential explicit levels may include:
- minimal;
- low;
- medium;
- high;
- max;
but do not assume every provider uses the same values or request fields.
Implement this through provider capabilities.
Requirements:
- expose only known-valid values when capabilities are known;
- preserve compatibility with unknown OpenAI-compatible providers;
- allow safe advanced configuration where appropriate;
- distinguish reasoning effort from thinking budget;
- distinguish token budgets from named effort levels;
- omit unsupported parameters;
- prevent mutually incompatible combinations;
- preserve providers with no reasoning support;
- show effective non-secret request settings in diagnostics or preview;
- migrate existing saved configurations safely.
Audit interactions among fields such as:
- reasoning effort;
- thinking budget;
- reasoning token count;
- output token limits;
- temperature;
- top-p;
- response format;
- streaming;
- provider-specific extra body fields.
Do not assume OpenAI, Anthropic-compatible gateways, Gemini-compatible gateways, DeepSeek-compatible endpoints, local servers, and miscellaneous OpenAI-compatible services use identical reasoning semantics.
Keep provider-specific request construction isolated behind the provider abstraction.
Do not leak API keys in diagnostics, exceptions, logs, screenshots, or persisted previews.
9. Dual-mode architecture
Audit and improve the boundary between shared core logic, the standalone application, and the Anki add-on.
Use clear layers for:
- domain models;
- application services;
- translation-practice logic;
- scoring;
- prompt rendering;
- provider capabilities;
- provider requests;
- response parsing;
- persistence;
- migration;
- Anki data access;
- UI presentation;
- platform integration.
Avoid duplicating major business logic between modes.
Platform-specific adapters should be thin.
Shared core modules should not import Anki-only or desktop-UI-only objects.
Avoid unnecessary broad rewrites. Refactor only where it materially improves correctness, testability, or compatibility.
10. User-interface integration
Integrate the new functionality into the existing product rather than adding disconnected experimental windows.
Provide coherent navigation for:
- generation from Anki reviews;
- translation practice from an existing article;
- translation practice from pasted text;
- article history;
- practice history;
- scoring configuration;
- prompt customization;
- API configuration;
- reasoning configuration.
Improve usability where needed:
- progress indicators;
- asynchronous requests;
- cancellation;
- recoverable errors;
- validation;
- safe dialog closure;
- unsaved-text preservation;
- confirmation before destructive actions;
- accessible labels;
- tooltips;
- basic and advanced settings separation;
- sensible defaults;
- clear unavailable-capability states.
Do not break:
- Japanese vertical reading;
- paragraph translation reveal;
- article export;
- saving to Anki;
- existing history browsing.
Avoid blocking either the standalone UI or Anki’s main UI during:
- model requests;
- AnkiConnect requests;
- scoring;
- long parsing;
- persistence operations where latency is meaningful.
11. Persistence and migration
Reuse the existing article-history and persistence implementation.
Extend it only where necessary to store new information such as:
- practice-session type;
- pasted source text;
- source language;
- target language;
- user translations;
- paragraph segmentation;
- segmentation edits;
- review attempts;
- AI feedback;
- scores;
- reference translations;
- custom instructions;
- prompt preset references;
- prompt snapshots;
- model settings;
- reasoning settings;
- timestamps;
- practice status;
- revision history.
Determine carefully which configuration should be:
- stored by reference;
- snapshotted for reproducibility;
- omitted for privacy or redundancy.
All migrations must be:
- backward-compatible;
- testable;
- non-destructive;
- tolerant of partial data;
- tolerant of corrupted optional fields;
- recoverable where practical.
Do not silently discard existing saved articles.
Do not unnecessarily discard unknown fields from newer or extended data formats.
Back up or checkpoint before risky migrations.
12. Reliability, privacy, and security
Audit reliability and security while implementing the release.
Requirements:
- do not log API keys;
- do not log pasted diary entries;
- do not log private articles;
- do not log user translations;
- do not log full model prompts by default;
- do not expose secrets in exception messages;
- preserve local-only API-key storage;
- redact sensitive request data from diagnostics;
- validate persisted settings;
- validate model responses;
- handle malformed network responses;
- handle cancellation;
- handle timeouts;
- handle partial writes;
- avoid corrupting history during crashes;
- avoid unnecessary heavyweight dependencies;
- avoid platform-specific assumptions in shared modules.
Fix architectural, error-handling, lifecycle, or privacy problems encountered during implementation when doing so is reasonably within scope.
Document material remaining risks honestly.
13. Testing
Add comprehensive tests.
At minimum, add or update unit tests for:
- translation-practice domain models;
- pasted-text sessions;
- paragraph segmentation;
- manual segmentation edits;
- reference-free translation review;
- reference-based back-translation review;
- review-response parsing;
- configurable scoring signals;
- enable and disable toggles;
- weights;
- normalization;
- contribution limits;
- nonlinear transformations where implemented;
- scoring with FSRS;
- scoring without FSRS;
- unavailable AnkiConnect data;
- score explanations;
- duplicate and sibling penalties;
- recent-reuse penalties;
- manual target inclusion and exclusion;
- required, preferred, optional, and excluded targets;
- prompt-template rendering;
- custom system prompts;
- custom user prompts;
- missing-variable validation;
- literal braces and escaping;
- plain-text prompt mode;
- structured-output prompt mode;
- provider capability detection;
- disabled reasoning;
- provider-default reasoning;
- explicit reasoning levels;
- incompatible API parameter prevention;
- provider request construction;
- response validation and fallback;
- article-history extension;
- practice-session persistence;
- migrations;
- corrupted optional data;
- capability detection;
- cancellation and lifecycle behavior where testable.
Add integration tests where practical for:
- standalone AnkiConnect adapter;
- add-on data adapter;
- normalized data conversion;
- standalone pasted-text workflow;
- standalone Anki-backed workflow;
- add-on workflow;
- generation pipeline;
- translation-review pipeline;
- persistence round trips;
- migrations;
- UI service boundaries.
Use mocks and fixtures where live Anki or external APIs are inappropriate.
Run:
- existing tests;
- new tests;
- static checks;
- type checks if configured;
- formatting checks;
- lint checks;
- packaging checks;
- import checks;
- any existing release or build scripts.
Do not report completion while known relevant tests are failing.
Do not merely document regressions that can reasonably be fixed.
After implementation, use fresh review subagents to search for missing tests and false-positive tests.
14. Documentation
Update documentation, including as applicable:
- README;
- feature overview;
- standalone installation;
- add-on installation;
- AnkiConnect setup;
- AnkiConnect troubleshooting;
- standalone versus add-on capability differences;
- pasted-text translation practice;
- article-based back-translation practice;
- scoring model;
- scoring presets;
- simple and advanced scoring controls;
- FSRS limitations;
- prompt customization;
- template variables;
- plain-text and structured prompt modes;
- reasoning settings;
- provider capability handling;
- privacy behavior;
- configuration migration;
- data migration;
- changelog;
- release notes;
- manual verification guide;
- screenshots or screenshot placeholders.
Documentation must not claim unsupported feature parity.
Document standard AnkiConnect limitations and actual fallbacks.
Suggested execution phases
Use these as a starting point, but adjust based on the actual repository architecture.
Phase 0: Repository safety and persistent state
- inspect git status and repository structure;
- preserve pre-existing changes;
- create canonical specification;
- create task ledger;
- identify supported environments;
- identify existing test and packaging commands;
- create a checkpoint commit.
Phase 1: Independent repository audit
Assign subagents to inspect:
- standalone/add-on architecture;
- existing history and persistence;
- model-provider abstraction;
- current prompts;
- Anki and AnkiConnect data access;
- UI architecture;
- test coverage;
- packaging and documentation.
Consolidate findings into the task ledger and architecture decisions.
Commit the audit documentation.
Phase 2: Shared domain and capability foundations
Implement through subagents:
- normalized Anki data models;
- capability model;
- practice-session models;
- provider reasoning capability models;
- necessary persistence extensions.
Add tests and migrations.
Commit each coherent unit.
Phase 3: Translation-practice core
Implement:
- existing-article practice;
- arbitrary pasted-text practice;
- segmentation;
- revision;
- AI review;
- reference-free review;
- reference-based comparison;
- persistence.
Add focused tests and commit coherent units.
Phase 4: Reinforcement-priority scoring
Implement:
- configurable signals;
- toggles;
- weights;
- normalization;
- explanation breakdown;
- FSRS optionality;
- duplicate and reuse handling;
- presets;
- manual selection controls.
Add tests and commit coherent units.
Phase 5: Prompt customization and provider reasoning
Implement:
- custom prompts;
- prompt preview;
- variables;
- structured and plain-text modes;
- preset migration;
- provider capabilities;
- disabled/default/explicit reasoning;
- incompatible parameter prevention.
Add tests and commit coherent units.
Phase 6: Platform adapters
Implement and verify:
- Anki add-on adapter;
- standard AnkiConnect adapter;
- capability degradation;
- disconnected desktop behavior;
- lifecycle and cancellation behavior.
Add tests and commit coherent units.
Phase 7: UI integration
Integrate all features coherently into both modes.
Preserve existing UI behavior.
Add service-boundary or UI tests where practical.
Commit coherent UI units rather than one enormous UI commit.
Phase 8: Documentation and migration verification
Update all required documentation.
Test migrations against representative old data.
Commit documentation and migration fixes.
Phase 9: Independent review
Launch fresh subagents that were not the primary implementers.
Assign separate reviews for:
- requirement coverage;
- architecture;
- standalone compatibility;
- add-on compatibility;
- persistence and migrations;
- provider request safety;
- privacy and security;
- UI behavior;
- tests;
- documentation.
Require reviewers to reread the canonical specification.
Record all findings in the task ledger.
Phase 10: Repair cycles
Dispatch repair subagents for all actionable findings.
After each repair group:
- run focused tests;
- commit fixes;
- update the task ledger;
- request targeted re-review.
Continue until no release-blocking issues remain.
Phase 11: Final release verification
Run the complete available test and check suite.
Inspect:
- git status;
- commit history;
- migrations;
- documentation;
- packaging;
- requirement matrix;
- known limitations.
Confirm that every completion criterion is either:
- satisfied;
- or documented as a concrete unavoidable limitation with the best viable implementation completed.
Do not leave uncommitted intended release changes.
Engineering constraints
- Inspect the existing repository before changing architecture.
- Preserve working systems.
- Reuse existing history and persistence.
- Prefer small and comprehensible modules.
- Prefer typed data structures where consistent with the codebase.
- Preserve backward compatibility unless a strong reason is documented.
- Keep UI, domain logic, persistence, provider logic, and Anki access separated.
- Keep platform-specific adapters thin.
- Keep provider-specific behavior capability-aware.
- Do not add unnecessary dependencies.
- Do not leave core functionality as TODOs, mocks, stubs, or pseudocode.
- Do not mark placeholder UI as complete functionality.
- Make reasonable product decisions autonomously.
- Document important decisions.
- Commit frequently in coherent units.
- Continue automatically after every phase and commit.
Completion criteria
The release is complete only when all of the following are satisfied:
1. Users can practise translation or back-translation from existing DAIRR articles.
2. Users can paste arbitrary source-language text and translate it.
3. Pasted-text practice works without Anki running.
4. Users can segment and edit source text.
5. Users can revise and resubmit translations.
6. AI review works without requiring verbatim reproduction.
7. AI review works without an official reference translation.
8. Existing history is preserved.
9. Practice sessions can be stored safely.
10. Reinforcement scoring supports configurable per-signal toggles.
11. Reinforcement scoring supports configurable weights.
12. The scoring system provides contribution explanations.
13. The scoring system works without FSRS.
14. Unavailable AnkiConnect data is represented honestly.
15. Users can preview and manually edit selected targets.
16. Required, preferred, optional, and excluded targets are supported.
17. Major AI prompts are fully customizable.
18. Final rendered prompts are previewable.
19. Mandatory technical wrappers are visible.
20. Plain-text prompt mode is supported where appropriate.
21. Reasoning can be completely disabled.
22. Disabled reasoning sends no reasoning parameter.
23. Provider default is distinct from disabled.
24. Explicit reasoning settings are capability-aware.
25. Invalid provider parameter combinations are prevented.
26. Standalone mode uses standard AnkiConnect rather than Anki internals.
27. Standalone mode handles AnkiConnect failure gracefully.
28. Add-on mode uses supported Anki APIs.
29. Long operations do not block the main UI.
30. Existing vertical reading and translation reveal continue to work.
31. Existing article generation and export continue to work.
32. Persistence migrations are backward-compatible and tested.
33. Privacy-sensitive text is not leaked into logs.
34. Existing and new tests pass.
35. Static, formatting, packaging, and import checks pass where configured.
36. Documentation is updated.
37. Requirement coverage has been independently reviewed.
38. Review findings have been repaired or explicitly justified.
39. Intended release changes are committed.
40. No core feature remains as an unimplemented placeholder.
Final response requirements
The main agent’s final response must provide a consolidated report containing:
- overall completion status;
- implemented features;
- subagents used and their responsibilities;
- major architectural decisions;
- standalone versus add-on behavior;
- standard AnkiConnect limitations and fallbacks;
- scoring design;
- prompt-customization design;
- provider reasoning design;
- persistence and migration changes;
- privacy and security changes;
- files or major modules changed;
- chronological list of commits with hashes and purposes;
- tests and checks executed;
- exact test results;
- independent review findings;
- fixes made after review;
- remaining limitations and risks;
- concise manual verification steps;
- current git status.
Do not claim completion merely because code was written.
Do not stop after creating a plan.
Do not stop after dispatching subagents.
Do not stop after the first implementation pass.
Do not stop after the first test pass.
Do not ask me to approve intermediate work.
Continue orchestrating, committing, testing, reviewing, repairing, and documenting until the release satisfies the completion criteria or a concrete environmental limitation makes further progress impossible.