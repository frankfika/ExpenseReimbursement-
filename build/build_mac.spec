# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['../desktop_app.py'],
    pathex=['../'],
    binaries=[],
    datas=[
        ('../web/templates', 'web/templates'),
        ('../web/static', 'web/static'),
    ],
    hiddenimports=[
        'webview',
        'flask',
        'paddleocr',
        'paddlepaddle',
        'PIL',
        'PIL._tkinter_finder',
        'openpyxl',
        'fitz',
        'pdf2image',
        'requests',
        'dotenv',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='报销助手',
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
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='报销助手',
)

app = BUNDLE(
    coll,
    name='报销助手.app',
    icon=None,
    bundle_identifier='com.expense.reimbursement',
    info_plist={
        'CFBundleName': '报销助手',
        'CFBundleDisplayName': '报销助手',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': '10.13.0',
    },
)
