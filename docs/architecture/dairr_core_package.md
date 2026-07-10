# DAIRR core package boundary

`packages/dairr_core` is the first-class Python package for DAIRR's shared
learning and article-generation logic. It is deliberately independent of
Anki's `aqt`/`mw` APIs, browser windows, and mobile bridges.

Hosts own platform concerns:

- The Anki add-on keeps its existing `daily_ai_reading_reinforcement.core.*`
  imports through thin compatibility wrappers. `package_addon.py` vendors the
  `dairr_core` package into the add-on archive.
- Desktop hosts import `dairr_core.*` normally. A small runtime path bootstrap
  makes the source package available during local development and from a
  PyInstaller data bundle; it does not install an import hook.
- `ConfigAdapter`, `DeckAdapter`, and `EnvironmentAdapter` remain the boundary
  between shared generation logic and shell-specific work.

New shared features belong in `dairr_core`. New shell, provider, storage, or
platform integrations belong outside it and communicate through explicit
adapter contracts.

## Learning-source contract (v1)

`dairr_core.learning_sources` defines the stable data boundary for every
learning application integrated with DAIRR. It includes source descriptors and
capabilities, source-scoped opaque IDs, deck/card snapshots, and a registry
that routes a deck ID to its owning source. The contract is platform-agnostic:
it has no HTTP, Anki, Android, or UI dependency.

Desktop currently adapts the existing AnkiConnect, MoMo, and demo providers
through `desktop_mock/learning_sources.py`. Bridge responses emit opaque IDs
such as `dairr:v1:momo:momo_today`; callers must treat them as opaque rather
than infer a provider from an ID prefix. A narrow primary-source fallback is
kept only to migrate older saved desktop selections. New sources should add a
host adapter implementing `LearningSource`, declare only capabilities they can
actually support, and register it with `LearningSourceRegistry`.
