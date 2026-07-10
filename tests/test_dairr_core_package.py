"""Architecture checks for the independently importable DAIRR core."""

from __future__ import annotations

import ast
import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CORE_SRC = ROOT / "packages" / "dairr_core" / "src"
if str(CORE_SRC) not in sys.path:
    sys.path.insert(0, str(CORE_SRC))


class TestDairrCorePackage(unittest.TestCase):
    def test_core_is_importable_without_an_addon_package(self) -> None:
        from dairr_core.config import DEFAULT_CONFIG
        from dairr_core.prompt import build_prompt

        self.assertEqual(DEFAULT_CONFIG["selected_provider_profile"], "openai")
        self.assertTrue(callable(build_prompt))

    def test_core_modules_do_not_import_anki_runtime(self) -> None:
        for module_path in (CORE_SRC / "dairr_core").glob("*.py"):
            tree = ast.parse(module_path.read_text(encoding="utf-8"))
            imports = [
                alias.name
                for node in ast.walk(tree)
                if isinstance(node, (ast.Import, ast.ImportFrom))
                for alias in node.names
            ]
            with self.subTest(module=module_path.name):
                self.assertFalse(any(name == "aqt" or name.startswith("aqt.") for name in imports))
                self.assertNotIn("mw", imports)

    def test_legacy_addon_core_wrapper_reexports_new_config(self) -> None:
        addon_root = ROOT / "addon" / "daily_ai_reading_reinforcement"
        sys.path.insert(0, str(addon_root))
        try:
            legacy_config = importlib.import_module("core.config")
            from dairr_core.config import DEFAULT_CONFIG

            self.assertIs(legacy_config.DEFAULT_CONFIG, DEFAULT_CONFIG)
        finally:
            sys.path.remove(str(addon_root))
