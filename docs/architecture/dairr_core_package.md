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
