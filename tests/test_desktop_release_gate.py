"""Release-gate and production packaging manifest tests."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
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
            "Android SDK-free JVM tests",
            "Browser desktop package dry-run",
            "Native desktop package dry-run",
            "Tauri sidecar package dry-run",
            "Tauri npm metadata",
            "Tauri Cargo check",
        } <= labels)

    def test_android_sdk_free_harness_compiles_production_sources_and_counts_seven(self) -> None:
        build = (ROOT / "apps/android/jvm-tests/build.gradle.kts").read_text(encoding="utf-8")
        for source in (
            "BridgeContract.kt",
            "BridgeDispatcher.kt",
            "AndroidPracticeRepository.kt",
        ):
            self.assertIn(source, build)
        self.assertIn('"../app/src/test/java"', build)

        runner_path = ROOT / "apps/android/tests/run_jvm_tests.py"
        spec = importlib.util.spec_from_file_location("dairr_android_jvm_runner_test", runner_path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        self.assertEqual(runner.EXPECTED_TESTS, 7)
        self.assertEqual(runner.java_major('openjdk version "17.0.19" 2026-04-21'), 17)
        self.assertEqual(runner.java_major('openjdk version "21.0.2"'), 21)
        self.assertEqual(runner.gradle_version("\nGradle 8.10.2\n"), (8, 10, 2))
        self.assertEqual(runner.gradle_version("Gradle 9.6.1\n"), (9, 6, 1))
        self.assertIsNone(runner.gradle_version("not Gradle output"))
        self.assertEqual(runner.SUPPORTED_GRADLE, {(8, 10, 2), (9, 6, 1)})
        candidates = runner.java17_candidates(None, {})
        self.assertIn(
            Path("/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home"),
            candidates,
        )
        with tempfile.TemporaryDirectory() as directory:
            reports = Path(directory)
            (reports / "TEST-one.xml").write_text(
                '<testsuite tests="4" failures="0" errors="0"/>', encoding="utf-8"
            )
            (reports / "TEST-two.xml").write_text(
                '<testsuite tests="3" failures="0" errors="0"/>', encoding="utf-8"
            )
            self.assertEqual(runner.count_results(reports), (7, 0, 0))

    def test_semver_validation_accepts_real_releases_and_rejects_invalid_versions(self) -> None:
        script = ROOT / "scripts" / "desktop_release.py"
        valid = (
            "0.1.0",
            "1.2.3",
            "10.20.30-alpha.1",
            "2.0.0-rc.1+build.20260716",
        )
        invalid = (
            "1.2",
            "01.2.3",
            "1.02.3",
            "1.2.03",
            "1.2.3-01",
            "1.2.3-",
            "1.2.3+",
            "1.2.3-alpha..1",
        )
        for version in valid:
            with self.subTest(valid=version):
                result = subprocess.run(
                    [sys.executable, str(script), "validate-version", "--version", version],
                    cwd=ROOT,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), version)
        for version in invalid:
            with self.subTest(invalid=version):
                result = subprocess.run(
                    [sys.executable, str(script), "validate-version", "--version", version],
                    cwd=ROOT,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_collect_artifacts_stages_mac_installer_and_updater_separately(self) -> None:
        mod = _release_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = root / "bundle"
            output = root / "release-assets"
            updater = bundle / "macos" / "DAIRR.app.tar.gz"
            updater.parent.mkdir(parents=True)
            updater.write_bytes(b"signed updater archive")
            updater.with_name(f"{updater.name}.sig").write_text("mac-signature\n", encoding="utf-8")
            dmg = bundle / "dmg" / "DAIRR_0.1.0_aarch64.dmg"
            dmg.parent.mkdir(parents=True)
            dmg.write_bytes(b"installable disk image")

            mod.collect_artifacts("darwin-aarch64", bundle, output)

            self.assertEqual(
                {path.name for path in output.iterdir()},
                {
                    "dairr-darwin-aarch64.app.tar.gz",
                    "dairr-darwin-aarch64.app.tar.gz.sig",
                    "dairr-darwin-aarch64.dmg",
                },
            )

    def test_collect_artifacts_stages_windows_installer_and_updater_signature(self) -> None:
        mod = _release_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = root / "bundle"
            output = root / "release-assets"
            installer = bundle / "nsis" / "DAIRR_0.1.0_x64-setup.exe"
            installer.parent.mkdir(parents=True)
            installer.write_bytes(b"signed nsis installer")
            installer.with_name(f"{installer.name}.sig").write_text(
                "windows-signature\n", encoding="utf-8"
            )

            mod.collect_artifacts("windows-x86_64", bundle, output)

            self.assertEqual(
                {path.name for path in output.iterdir()},
                {
                    "dairr-windows-x86_64-setup.exe",
                    "dairr-windows-x86_64-setup.exe.sig",
                },
            )

    def test_artifact_staging_rejects_empty_assets_and_blank_signatures(self) -> None:
        mod = _release_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = root / "bundle"
            output = root / "output"
            updater = bundle / "macos" / "DAIRR.app.tar.gz"
            updater.parent.mkdir(parents=True)
            updater.write_bytes(b"")
            updater.with_name(f"{updater.name}.sig").write_text("signature\n", encoding="utf-8")
            dmg = bundle / "dmg" / "DAIRR.dmg"
            dmg.parent.mkdir(parents=True)
            dmg.write_bytes(b"installer")
            with self.assertRaisesRegex(ValueError, "updater artifact is empty"):
                mod.collect_artifacts("darwin-aarch64", bundle, output)

            updater.write_bytes(b"updater")
            updater.with_name(f"{updater.name}.sig").write_text("  \n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "signature is blank"):
                mod.collect_artifacts("darwin-aarch64", bundle, output)

            updater.with_name(f"{updater.name}.sig").write_text("signature\n", encoding="utf-8")
            dmg.write_bytes(b"")
            with self.assertRaisesRegex(ValueError, "macOS installer is empty"):
                mod.collect_artifacts("darwin-aarch64", bundle, output)

    def test_latest_json_uses_updater_archives_not_mac_installers(self) -> None:
        mod = _release_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for target in mod.REQUIRED_TARGETS:
                if target.startswith("darwin-"):
                    artifact = root / f"dairr-{target}.app.tar.gz"
                    (root / f"dairr-{target}.dmg").write_bytes(b"installer")
                else:
                    artifact = root / f"dairr-{target}-setup.exe"
                artifact.write_bytes(b"updater")
                artifact.with_name(f"{artifact.name}.sig").write_text(
                    f"signature-{target}\n", encoding="utf-8"
                )
            output = root / "latest.json"

            mod.latest_json("1.2.3", "https://example.test/v1.2.3", root, output, "notes")

            manifest = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(set(manifest["platforms"]), set(mod.REQUIRED_TARGETS))
            urls = [entry["url"] for entry in manifest["platforms"].values()]
            self.assertFalse(any(url.endswith(".dmg") for url in urls))
            self.assertTrue(any(url.endswith(".app.tar.gz") for url in urls))

    def test_latest_json_requires_nonempty_publishable_dmgs_and_signatures(self) -> None:
        mod = _release_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for target in mod.REQUIRED_TARGETS:
                if target.startswith("darwin-"):
                    artifact = root / f"dairr-{target}.app.tar.gz"
                    (root / f"dairr-{target}.dmg").write_bytes(b"installer")
                else:
                    artifact = root / f"dairr-{target}-setup.exe"
                artifact.write_bytes(b"updater")
                artifact.with_name(f"{artifact.name}.sig").write_text("signature\n", encoding="utf-8")

            (root / "dairr-darwin-x86_64.dmg").write_bytes(b"")
            with self.assertRaisesRegex(ValueError, "darwin-x86_64 installer is empty"):
                mod.latest_json("1.2.3", "https://example.test/v1.2.3", root, root / "latest.json", "notes")

            (root / "dairr-darwin-x86_64.dmg").write_bytes(b"installer")
            (root / "dairr-windows-x86_64-setup.exe.sig").write_text("\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "signature is blank"):
                mod.latest_json("1.2.3", "https://example.test/v1.2.3", root, root / "latest.json", "notes")

    def test_release_gate_rejects_tracked_generated_outputs(self) -> None:
        mod = _release_module()
        self.assertEqual(
            mod.generated_output_paths(
                [
                    "README.md",
                    "build/DAIRR/Analysis-00.toc",
                    "dist/DAIRR.app/Contents/MacOS/DAIRR",
                    "release-assets/latest.json",
                    "apps/desktop/src-tauri/target/release/dairr-desktop",
                    "apps/desktop/src-tauri/binaries/README.md",
                    "apps/desktop/src-tauri/binaries/dairr-backend/.gitkeep",
                    "apps/desktop/src-tauri/binaries/dairr-backend/backend.exe",
                    "apps/desktop/src-tauri/binaries/dairr-backend-aarch64-apple-darwin",
                ]
            ),
            [
                "apps/desktop/src-tauri/binaries/dairr-backend-aarch64-apple-darwin",
                "apps/desktop/src-tauri/binaries/dairr-backend/backend.exe",
                "apps/desktop/src-tauri/target/release/dairr-desktop",
                "build/DAIRR/Analysis-00.toc",
                "dist/DAIRR.app/Contents/MacOS/DAIRR",
                "release-assets/latest.json",
            ],
        )
        self.assertEqual(mod.tracked_generated_outputs(), [])
        mod.assert_no_tracked_generated_outputs()

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
        self.assertIn('--check-runtime', workflow)
        self.assertIn('uses: actions/setup-java@v4', workflow)
        self.assertIn('uses: gradle/actions/setup-gradle@v4', workflow)
        self.assertIn('gradle-version: "8.10.2"', workflow)
        self.assertIn("files: release-assets/*", workflow)
        self.assertIn(
            'VERSION="$(python3 scripts/desktop_release.py validate-version --version "$VERSION")"',
            workflow,
        )
        self.assertIn("DISPATCH_VERSION: ${{ inputs.version }}", workflow)
        self.assertIn('VERSION="$DISPATCH_VERSION"', workflow)
        self.assertNotIn('VERSION="${{ inputs.version }}"', workflow)
        self.assertNotIn("re.fullmatch", workflow)
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
            "apps/desktop/src-tauri/binaries/dairr-backend-*",
        ):
            with self.subTest(pattern=pattern):
                self.assertIn(pattern, ignore)

    def test_sidecar_documentation_matches_onedir_and_authenticated_bridge_contract(self) -> None:
        readme = (ROOT / "apps/desktop/src-tauri/binaries/README.md").read_text(encoding="utf-8")
        self.assertIn("binaries/dairr-backend/dairr-backend", readme)
        self.assertIn("X-DAIRR-Bridge-Token", readme)
        self.assertIn("Origin: http://127.0.0.1:8755", readme)
        self.assertNotIn("dairr-backend-aarch64-apple-darwin", readme)
        self.assertNotIn("dairr-backend-x86_64-pc-windows-msvc.exe", readme)

    def test_apple_release_docs_match_the_implemented_notarization_inputs(self) -> None:
        documentation = (ROOT / "docs/desktop_auto_updates.md").read_text(encoding="utf-8")
        self.assertIn("workflow derives\n  `APPLE_SIGNING_IDENTITY`", documentation)
        self.assertIn("it is not a separate repository secret", documentation)
        self.assertIn("Apple-ID/app-specific\n  password notarization method currently implemented", documentation)
        self.assertIn("API-key\n  notarization is not claimed", documentation)


if __name__ == "__main__":
    unittest.main()
