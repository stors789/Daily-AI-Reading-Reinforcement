# dairr-core

`dairr-core` contains DAIRR's platform-agnostic configuration, prompt,
rendering, LLM, and adapter-driven article-generation code. It deliberately
does not import Anki, desktop-shell, or mobile-shell APIs.

For local development, install it with:

```sh
python3 -m pip install -e packages/dairr_core
```

The Anki add-on retains its legacy `daily_ai_reading_reinforcement.core.*`
imports through compatibility wrappers. Packaging vendors this package beside
the add-on entry point.

`dairr_core.learning_sources` provides the versioned v1 learning-source
contract: source descriptors/capabilities, opaque source-scoped IDs, study
deck/card snapshots, and source routing. Provider transport remains in host
adapters, so the same contract can serve desktop, add-on, and mobile shells.
