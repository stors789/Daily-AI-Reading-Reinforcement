"""Release-gate and production packaging manifest tests."""

from __future__ import annotations

import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path

import package_desktop
import package_tauri_sidecar


ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "release-desktop.yml"


def _release_module():
    path = ROOT / "scripts" / "desktop_release.py"
    spec = importlib.util.spec_from_file_location("dairr_release_gate_test", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DesktopPackagingManifestTests(unittest.TestCase):
    def test_checked_in_pyinstaller_spec_is_portable_and_uses_reviewed_manifest(self) -> None:
        content = (ROOT / "DAIRR.spec").read_text(encoding="utf-8")
        self.assertNotIn("/Users/", content)
        self.assertIn("Path(SPECPATH).resolve()", content)
        self.assertIn('"ankiconnect_data_adapter.py"', content)
        self.assertIn('CORE_DIR.glob("*.py")', content)
        self.assertIn("WEB_SUFFIXES", content)

    def test_both_packagers_include_all_core_modules_web_assets_and_desktop_adapter(self) -> None:
        expected_core = set((ROOT / "packages/dairr_core/src/dairr_core").glob("*.py"))
        expected_web = {
            ROOT / "addon/daily_ai_reading_reinforcement/web" / name
            for name in ("index.html", "style.css", "app.js")
        }
        for module in (package_desktop, package_tauri_sidecar):
            with self.subTest(packager=module.__name__):
                sources = {source for source, _destination in module.DATA_PATHS}
                self.assertTrue(expected_core <= sources)
                self.assertTrue(expected_web <= sources)
                self.assertIn(
                    ROOT / "desktop_mock/ankiconnect_data_adapter.py",
                    sources,
                )

    def test_packaging_manifests_contain_only_files_and_no_private_runtime_state(self) -> None:
        forbidden_parts = {
            "__pycache__", "build", "dist", "node_modules", "output",
            "user_files", "practice_sessions",
        }
        for module in (package_desktop, package_tauri_sidecar):
            for source, destination in module.DATA_PATHS:
                with self.subTest(packager=module.__name__, source=source):
                    self.assertTrue(source.is_file())
                    self.assertTrue(source.is_relative_to(ROOT))
                    self.assertFalse(forbidden_parts.intersection(source.relative_to(ROOT).parts))
                    self.assertFalse(forbidden_parts.intersection(destination.parts))
                    self.assertNotIn(source.suffix.lower(), {".db", ".log", ".pyc", ".sqlite"})

    def test_pyinstaller_outputs_are_confined_to_ignored_build_and_dist_directories(self) -> None:
        command = package_desktop.build_pyinstaller_command(entry="native", name="DAIRR")
        self.assertIn(str(ROOT / "dist"), command)
        self.assertIn(str(ROOT / "build/pyinstaller-work"), command)
        self.assertIn(str(ROOT / "build/pyinstaller-specs"), command)


class DesktopReleaseGateTests(unittest.TestCase):
    def test_checked_in_release_metadata_is_safe_and_synchronized(self) -> None:
        self.assertEqual(_release_module().assert_checked_in_release_config_safe(), "0.1.0")

    def test_gate_covers_required_release_surfaces(self) -> None:
        checks = _release_module().pre_publish_checks()
        labels = {label for label, _command, _cwd, _tool in checks}
        self.assertTrue({
            "Python compile",
            "Production imports",
            "Full unittest suite",
            "Add-on package privacy",
            "Portable web UI static tests",
            "Web JavaScript syntax",
            "Android static validator",
            "Browser desktop package dry-run",
            "Native desktop package dry-run",
            "Tauri sidecar package dry-run",
            "Tauri npm metadata",
            "Tauri Cargo check",
        } <= labels)

    def test_version_sync_updates_cargo_lock_with_every_other_manifest(self) -> None:
        mod = _release_module()
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            for attribute in (
                "RELEASE_METADATA_PATH", "TAURI_CONFIG_PATH", "CARGO_TOML_PATH",
                "CARGO_LOCK_PATH", "PACKAGE_JSON_PATH", "PACKAGE_LOCK_PATH",
            ):
                source = getattr(mod, attribute)
                destination = temporary / source.name
                shutil.copy2(source, destination)
                setattr(mod, attribute, destination)
            mod.sync_version("1.2.3")
            self.assertEqual(set(mod.configured_versions().values()), {"1.2.3"})

    def test_release_workflow_blocks_native_builds_on_pre_publish_gate(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("pre-publish:", workflow)
        self.assertIn("python3 scripts/desktop_release.py pre-publish", workflow)
        self.assertIn("needs: [verify-release, pre-publish]", workflow)
        self.assertIn("runner: macos-15-intel", workflow)
        self.assertNotIn("runner: macos-13", workflow)
        self.assertIn('python package_tauri_sidecar.py --target-triple', workflow)
        self.assertNotIn("base64 --decode", workflow)
        self.assertLess(
            workflow.index("python3 scripts/desktop_release.py pre-publish"),
            workflow.index("Build native Python sidecar"),
        )

    def test_generated_and_private_root_outputs_are_ignored(self) -> None:
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        for pattern in (
            "build/", "config/", "dist/", "release-assets/",
            "apps/desktop/src-tauri/target/", "apps/desktop/node_modules/",
        ):
            with self.subTest(pattern=pattern):
                self.assertIn(pattern, ignore)


if __name__ == "__main__":
    unittest.main()
