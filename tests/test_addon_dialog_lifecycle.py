from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock


ROOT = Path(__file__).resolve().parent.parent
for path in (
    ROOT / "packages" / "dairr_core" / "src",
    ROOT / "addon" / "daily_ai_reading_reinforcement",
):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from dialog_lifecycle import (  # noqa: E402
    invalidate_all,
    register,
    register_supported_hooks,
    unregister,
)


class _Hooks:
    def __init__(self):
        self.profile_will_close = []
        self.collection_will_close = []


class AddonDialogLifecycleTests(unittest.TestCase):
    def test_invalidate_all_uses_weak_manager_registry(self) -> None:
        manager = Mock()
        register(manager)
        invalidate_all()
        manager.invalidate.assert_called_once_with()
        unregister(manager)

    def test_supported_hooks_register_once(self) -> None:
        hooks = _Hooks()
        self.assertEqual(
            register_supported_hooks(hooks),
            ("profile_will_close", "collection_will_close"),
        )
        self.assertEqual(register_supported_hooks(hooks), ())
        self.assertEqual(hooks.profile_will_close, [invalidate_all])
        self.assertEqual(hooks.collection_will_close, [invalidate_all])


if __name__ == "__main__":
    unittest.main()
