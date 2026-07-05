"""Anki-specific config store adapter.

Wraps mw.addonManager.getConfig / writeConfig so the rest of the add-on
can read and write configuration through a single object.  This file is
allowed to import aqt / mw because it is an adapter, not core logic.
"""

from __future__ import annotations

from typing import Any

from aqt import mw


class AnkiConfigStore:
    """Thin adapter over Anki's mw.addonManager config API."""

    def __init__(self, addon_name: str) -> None:
        self._addon_name = addon_name

    def load(self) -> dict[str, Any] | None:
        """Return the raw config dict stored in Anki, or None."""
        return mw.addonManager.getConfig(self._addon_name)

    def save(self, config: dict[str, Any]) -> None:
        """Persist *config* via Anki's addonManager."""
        mw.addonManager.writeConfig(self._addon_name, config)
