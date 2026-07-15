# -*- mode: python ; coding: utf-8 -*-
"""Portable PyInstaller spec for the transitional native desktop launcher."""

import sys
from pathlib import Path


ROOT = Path(SPECPATH).resolve()
CORE_DIR = ROOT / "packages" / "dairr_core" / "src" / "dairr_core"
WEB_DIR = ROOT / "addon" / "daily_ai_reading_reinforcement" / "web"
DESKTOP_MODULES = (
    "ankiconnect_card_saver.py",
    "ankiconnect_data_adapter.py",
    "ankiconnect_provider.py",
    "desktop_adapters.py",
    "dairr_core_runtime.py",
    "desktop_paths.py",
    "diagnostics.py",
    "learning_sources.py",
    "main.py",
    "mock_data.py",
    "momo_provider.py",
    "real_momo_provider.py",
)
WEB_SUFFIXES = {".css", ".html", ".js", ".svg", ".png", ".ico", ".webp"}

datas = [(str(path), "dairr_core") for path in sorted(CORE_DIR.glob("*.py"))]
datas.extend(
    (str(path), str(Path("addon/daily_ai_reading_reinforcement/web") / path.relative_to(WEB_DIR).parent))
    for path in sorted(WEB_DIR.rglob("*"))
    if path.is_file() and path.suffix.lower() in WEB_SUFFIXES
)
datas.extend((str(ROOT / "desktop_mock" / name), "desktop_mock") for name in DESKTOP_MODULES)

icon = ROOT / "assets" / "branding" / ("icon.ico" if sys.platform.startswith("win") else "icon.icns")
icon_value = str(icon) if icon.is_file() else None

a = Analysis(
    [str(ROOT / "desktop_native.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=["datetime", "http.server", "urllib.error", "urllib.request", "uuid", "webview"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DAIRR",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_value,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="DAIRR",
)
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="DAIRR.app",
        icon=icon_value,
        bundle_identifier="com.dairr.desktop",
    )
