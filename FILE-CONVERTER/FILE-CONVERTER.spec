# -*- mode: python ; coding: utf-8 -*-
# FILE-CONVERTER 用の PyInstaller 設定。
#
# リファクタリング後も入口は converter-main.py のままなので、
# Analysis の対象ファイルは変えていない。core / converters パッケージは
# converter-main.py -> core.app -> converters.registry -> converters.pdf_to_image
# と静的に import されるため、通常は自動で収集される。
# ただし将来、変換機を動的に読み込むようになった場合に備え、
# 組み込みの変換機を hiddenimports にも明示しておく。
# ビルドし直すときは build/ と dist/ は .gitignore で除外される。


a = Analysis(
    ['converter-main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['converters.pdf_to_image'],
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
    a.binaries,
    a.datas,
    [],
    name='FILE-CONVERTER',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['converter.ico'],
)
