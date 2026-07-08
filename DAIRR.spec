# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['/Users/eros/Documents/Daily AI Reading Reinforcement/desktop_app.py'],
    pathex=[],
    binaries=[],
    datas=[('/Users/eros/Documents/Daily AI Reading Reinforcement/addon/daily_ai_reading_reinforcement/core', 'addon/daily_ai_reading_reinforcement/core'), ('/Users/eros/Documents/Daily AI Reading Reinforcement/addon/daily_ai_reading_reinforcement/web', 'addon/daily_ai_reading_reinforcement/web'), ('/Users/eros/Documents/Daily AI Reading Reinforcement/desktop_mock/ankiconnect_card_saver.py', 'desktop_mock'), ('/Users/eros/Documents/Daily AI Reading Reinforcement/desktop_mock/ankiconnect_provider.py', 'desktop_mock'), ('/Users/eros/Documents/Daily AI Reading Reinforcement/desktop_mock/desktop_adapters.py', 'desktop_mock'), ('/Users/eros/Documents/Daily AI Reading Reinforcement/desktop_mock/desktop_paths.py', 'desktop_mock'), ('/Users/eros/Documents/Daily AI Reading Reinforcement/desktop_mock/diagnostics.py', 'desktop_mock'), ('/Users/eros/Documents/Daily AI Reading Reinforcement/desktop_mock/main.py', 'desktop_mock'), ('/Users/eros/Documents/Daily AI Reading Reinforcement/desktop_mock/mock_data.py', 'desktop_mock'), ('/Users/eros/Documents/Daily AI Reading Reinforcement/desktop_mock/momo_provider.py', 'desktop_mock'), ('/Users/eros/Documents/Daily AI Reading Reinforcement/desktop_mock/real_momo_provider.py', 'desktop_mock')],
    hiddenimports=['datetime', 'http.server', 'urllib.error', 'urllib.request', 'uuid'],
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
    name='DAIRR',
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
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='DAIRR',
)
app = BUNDLE(
    coll,
    name='DAIRR.app',
    icon=None,
    bundle_identifier=None,
)
