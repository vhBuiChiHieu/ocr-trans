# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:\\Users\\Admin\\Desktop\\work\\orc-trans-app\\main.py'],
    pathex=[],
    binaries=[],
    datas=[('C:\\Users\\Admin\\Desktop\\work\\orc-trans-app\\scripts\\google_translate.py', 'scripts'), ('C:\\Users\\Admin\\Desktop\\work\\orc-trans-app\\scripts\\google_translate_web_tokens.json', 'scripts')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pytest', 'tkinter', 'matplotlib', 'IPython', 'jupyter', 'notebook', 'cupy', 'tensorrt', 'torch', 'torchvision', 'torchaudio', 'tensorflow', 'keras', 'onnx', 'onnxruntime', 'nvidia'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='orc-trans-app',
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
    name='orc-trans-app',
)
