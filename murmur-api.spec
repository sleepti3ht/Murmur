# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['dashboard/api.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=['murmur', 'murmur.core', 'murmur.core.detector', 'murmur.core.models', 'murmur.core.scoring', 'murmur.core.entropy', 'murmur.core.baseline', 'murmur.storage', 'murmur.storage.sqlite', 'murmur.adapters', 'murmur.adapters.git_hook', 'murmur.adapters.git_push', 'murmur.adapters.history', 'murmur.alerting', 'murmur.alerting.console', 'murmur.external_scan'],
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
    name='murmur-api',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
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
    name='murmur-api',
)
