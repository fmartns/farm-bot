# -*- mode: python ; coding: utf-8 -*-
# Build: pyinstaller farm_bot.spec
# Gera dist/FARM BOT/FARM BOT.exe (modo onedir).

a = Analysis(
    ['farm_bot.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'mss',
        'mss.windows',
        'pydirectinput',
    ],
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
    name='FARM BOT',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
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
    upx=False,
    upx_exclude=[],
    name='FARM BOT',
)
