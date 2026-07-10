from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
TAURI_DIR = ROOT / "apps" / "desktop"
SRC_TAURI_DIR = TAURI_DIR / "src-tauri"
WEB_DIR = ROOT / "addon" / "daily_ai_reading_reinforcement" / "web"
BINARIES_DIR = SRC_TAURI_DIR / "binaries"


class _AssetParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.assets: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if name in {"src", "href"} and value:
                self.assets.append(value)


def _load_desktop_mock_main():
    mock_dir = ROOT / "desktop_mock"
    if str(mock_dir) not in sys.path:
        sys.path.insert(0, str(mock_dir))
    spec = importlib.util.spec_from_file_location(
        "dairr_tauri_test_desktop_mock_main",
        mock_dir / "main.py",
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load desktop_mock/main.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TauriAppShellTests(unittest.TestCase):
    def test_tauri_project_files_exist(self) -> None:
        expected = [
            TAURI_DIR / "package.json",
            SRC_TAURI_DIR / "Cargo.toml",
            SRC_TAURI_DIR / "build.rs",
            SRC_TAURI_DIR / "tauri.conf.json",
            SRC_TAURI_DIR / "src" / "main.rs",
            SRC_TAURI_DIR / "capabilities" / "default.json",
            SRC_TAURI_DIR / "icons" / "icon.png",
        ]
        for path in expected:
            with self.subTest(path=path):
                self.assertTrue(path.exists(), f"missing {path}")

    def test_tauri_config_points_at_existing_backend_boundary(self) -> None:
        config = json.loads((SRC_TAURI_DIR / "tauri.conf.json").read_text())
        self.assertEqual(config["build"]["devUrl"], "http://127.0.0.1:8755")
        self.assertEqual(config["build"]["frontendDist"], "http://127.0.0.1:8755")
        self.assertEqual(config["identifier"], "com.dairr.desktop")
        self.assertEqual(config["app"]["windows"], [])
        self.assertIn("../../../desktop_mock", config["build"]["additionalWatchFolders"])
        self.assertIn(
            "../../../addon/daily_ai_reading_reinforcement/web",
            config["build"]["additionalWatchFolders"],
        )

    def test_tauri_config_prepares_bundle_sidecar_boundary(self) -> None:
        config = json.loads((SRC_TAURI_DIR / "tauri.conf.json").read_text())
        self.assertTrue(config["bundle"]["active"])
        self.assertIn("icons/icon.icns", config["bundle"]["icon"])
        self.assertIn("icons/icon.ico", config["bundle"]["icon"])
        self.assertEqual(config["bundle"]["resources"], ["binaries/dairr-backend"])
        self.assertNotIn("signingIdentity", config["bundle"].get("macOS", {}))
        self.assertNotIn("certificateThumbprint", config["bundle"].get("windows", {}))
        self.assertTrue((SRC_TAURI_DIR / "binaries" / "README.md").exists())

    def test_rust_shell_bootstraps_existing_python_backend(self) -> None:
        main_rs = (SRC_TAURI_DIR / "src" / "main.rs").read_text()
        self.assertIn("desktop_app.py", main_rs)
        self.assertIn("--no-browser", main_rs)
        self.assertIn("DAIRR_REPO_ROOT", main_rs)
        self.assertIn("DAIRR_DESKTOP_PROVIDER", main_rs)
        self.assertIn("DAIRR_ANKICONNECT_URL", main_rs)
        self.assertIn("WebviewUrl::CustomProtocol", main_rs)
        self.assertIn('register_uri_scheme_protocol("dairr-startup"', main_rs)
        self.assertIn("window.navigate", main_rs)

    def test_rust_shell_starts_backend_off_setup_thread_without_fatal_error(self) -> None:
        main_rs = (SRC_TAURI_DIR / "src" / "main.rs").read_text()
        self.assertIn("thread::spawn", main_rs)
        self.assertIn("Duration::from_secs(45)", main_rs)
        self.assertIn("creating startup window before backend wait", main_rs)
        self.assertIn("Startup window creation failed", main_rs)
        self.assertNotIn(".build()?;", main_rs)
        self.assertNotIn("stop_child(child);\n                    return Err", main_rs)
        self.assertIn("DAIRR 没有崩溃", main_rs)

    def test_rust_shell_requires_health_check_before_reusing_port(self) -> None:
        main_rs = (SRC_TAURI_DIR / "src" / "main.rs").read_text()
        self.assertIn("/api/health", main_rs)
        self.assertIn("request_backend_health", main_rs)
        self.assertIn("DAIRR_APP_ID", main_rs)
        self.assertIn("port {} is already in use", main_rs)
        self.assertIn("bridge_available", main_rs)
        self.assertIn("instanceId", main_rs)
        self.assertIn("health.instance_id == instance_id", main_rs)

    def test_rust_shell_stops_owned_pyinstaller_process_group(self) -> None:
        main_rs = (SRC_TAURI_DIR / "src" / "main.rs").read_text()
        self.assertIn("--parent-pid", main_rs)
        self.assertIn("--shutdown-token", main_rs)
        self.assertIn("/api/shutdown", main_rs)
        self.assertIn("process_group(0)", main_rs)
        self.assertIn("libc::kill(-process.process_group", main_rs)
        self.assertIn("health.instance_id != process.instance_id", main_rs)

    def test_rust_shell_has_dev_python_and_production_sidecar_paths(self) -> None:
        main_rs = (SRC_TAURI_DIR / "src" / "main.rs").read_text()
        self.assertIn("DAIRR_BACKEND_MODE", main_rs)
        self.assertIn("DAIRR_BACKEND_SIDECAR", main_rs)
        self.assertIn("SIDECAR_BASENAME", main_rs)
        self.assertIn("SIDECAR_TARGET_TRIPLE", main_rs)
        self.assertIn("sidecar_target_triple_filename", main_rs)
        self.assertIn("start_bundled_backend", main_rs)
        self.assertIn("start_python_backend", main_rs)

    def test_shared_web_ui_resources_exist_and_inline_for_desktop_backend(self) -> None:
        for filename in ["index.html", "style.css", "app.js"]:
            with self.subTest(filename=filename):
                self.assertTrue((WEB_DIR / filename).exists())

        desktop_main = _load_desktop_mock_main()
        page = desktop_main._build_index_page()
        self.assertIn("<style>", page)
        self.assertIn('window.__DAIRR_BRIDGE__', page)
        self.assertIn('fetch("/api/bridge"', page)
        self.assertIn('<main class="app-shell">', page)

    def test_web_index_local_asset_references_are_not_broken(self) -> None:
        parser = _AssetParser()
        parser.feed((WEB_DIR / "index.html").read_text())

        for asset in parser.assets:
            if asset.startswith(("http://", "https://", "data:", "#")):
                continue
            with self.subTest(asset=asset):
                self.assertTrue((WEB_DIR / asset).exists(), f"missing asset {asset}")

class TauriSidecarTests(unittest.TestCase):
    def test_sidecar_placeholder_files_exist_with_target_triple_names(self) -> None:
        expected_placeholders = [
            "dairr-backend-aarch64-apple-darwin",
            "dairr-backend-x86_64-apple-darwin",
            "dairr-backend-x86_64-pc-windows-msvc.exe",
        ]
        for name in expected_placeholders:
            with self.subTest(name=name):
                path = BINARIES_DIR / name
                self.assertTrue(path.exists(), f"missing {{path}}")

    def test_sidecar_build_script_exists_and_is_runnable(self) -> None:
        script = ROOT / "package_tauri_sidecar.py"
        self.assertTrue(script.exists(), f"missing {{script}}")
        content = script.read_text()
        self.assertIn("detect_target_triple", content)
        self.assertIn("sidecar_filename", content)
        self.assertIn("sidecar_output_path", content)
        self.assertIn("sidecar_runtime_path", content)
        self.assertIn("is_placeholder", content)
        self.assertIn("build_pyinstaller_command", content)
        self.assertIn("run_packager", content)

    def test_sidecar_script_target_triple_naming_rules(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "dairr_sidecar_triple_test",
            ROOT / "package_tauri_sidecar.py",
        )
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        self.assertEqual(
            mod.sidecar_filename("aarch64-apple-darwin"),
            "dairr-backend-aarch64-apple-darwin",
        )
        self.assertEqual(
            mod.sidecar_filename("x86_64-apple-darwin"),
            "dairr-backend-x86_64-apple-darwin",
        )
        self.assertEqual(
            mod.sidecar_filename("x86_64-pc-windows-msvc"),
            "dairr-backend-x86_64-pc-windows-msvc.exe",
        )

        output_mac = mod.sidecar_output_path("aarch64-apple-darwin")
        self.assertTrue(str(output_mac).endswith("dairr-backend-aarch64-apple-darwin"))

        output_win = mod.sidecar_output_path("x86_64-pc-windows-msvc")
        self.assertTrue(str(output_win).endswith("dairr-backend-x86_64-pc-windows-msvc.exe"))
        runtime_mac = mod.sidecar_runtime_path("aarch64-apple-darwin")
        self.assertTrue(str(runtime_mac).endswith("dairr-backend/dairr-backend"))
        runtime_win = mod.sidecar_runtime_path("x86_64-pc-windows-msvc")
        self.assertTrue(str(runtime_win).endswith("dairr-backend/dairr-backend.exe"))

    def test_sidecar_script_dry_run_outputs_expected_artifacts(self) -> None:
        from io import StringIO
        spec = importlib.util.spec_from_file_location(
            "dairr_sidecar_dry_run_test",
            ROOT / "package_tauri_sidecar.py",
        )
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        stdout = StringIO()
        exit_code = mod.run_packager(
            ["--target-triple", "aarch64-apple-darwin", "--dry-run"],
            stdout=stdout,
        )
        self.assertEqual(exit_code, 0)
        output = stdout.getvalue()
        self.assertIn("--name dairr-backend", output)
        self.assertIn("--onedir", output)
        self.assertIn("--console", output)
        self.assertIn("desktop_app.py", output)
        self.assertIn("addon/daily_ai_reading_reinforcement/core", output)
        self.assertIn("desktop_mock/main.py", output)

    def test_sidecar_script_known_target_triples_are_valid(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "dairr_sidecar_triples_test",
            ROOT / "package_tauri_sidecar.py",
        )
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        for triple in ["aarch64-apple-darwin", "x86_64-apple-darwin", "x86_64-pc-windows-msvc"]:
            with self.subTest(triple=triple):
                self.assertIn(triple, mod.TARGET_TRIPLES)

    def test_placeholder_detection_on_known_placeholder(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "dairr_sidecar_placeholder_test",
            ROOT / "package_tauri_sidecar.py",
        )
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        win_placeholder = BINARIES_DIR / "dairr-backend-x86_64-pc-windows-msvc.exe"
        if win_placeholder.exists():
            self.assertTrue(
                mod.is_placeholder(win_placeholder),
                f"Expected {{win_placeholder}} to be detected as placeholder",
            )



if __name__ == "__main__":
    unittest.main()
