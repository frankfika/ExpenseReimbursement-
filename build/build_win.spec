# -*- mode: python ; coding: utf-8 -*-
# 报销助手 - Windows 打包配置

import sys
import os
from pathlib import Path

block_cipher = None

# 项目根目录
project_root = Path(SPECPATH).parent

a = Analysis(
    [str(project_root / 'desktop_app.py')],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        # Web 资源
        (str(project_root / 'web' / 'templates'), 'web/templates'),
        (str(project_root / 'web' / 'static'), 'web/static'),
        # app 模块
        (str(project_root / 'app'), 'app'),
    ],
    hiddenimports=[
        # Flask 相关
        'flask',
        'flask.json',
        'flask.templating',
        'jinja2',
        'werkzeug',
        'werkzeug.serving',
        'werkzeug.debug',
        'itsdangerous',
        'click',
        'markupsafe',
        # Webview - Windows
        'webview',
        'webview.platforms',
        'webview.platforms.edgechromium',
        'webview.platforms.mshtml',
        'webview.platforms.cef',
        # 核心功能
        'PIL',
        'PIL._tkinter_finder',
        'PIL.Image',
        'openpyxl',
        'openpyxl.workbook',
        'openpyxl.worksheet',
        'fitz',  # PyMuPDF
        'requests',
        'dotenv',
        'python-dotenv',
        # PaddleOCR 相关
        'paddleocr',
        'paddlepaddle',
        'paddle',
        'paddle.fluid',
        'numpy',
        'cv2',
        'shapely',
        'pyclipper',
        'imgaug',
        'lmdb',
        'rapidfuzz',
        # 其他
        'threading',
        'pathlib',
        'json',
        'uuid',
        'tempfile',
        'zipfile',
        'shutil',
        'atexit',
        'datetime',
        'logging',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除不需要的模块以减小体积
        'tkinter',
        'matplotlib',
        'IPython',
        'jupyter',
        'notebook',
    ],
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
    name='ExpenseHelper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # 无控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # 可以添加 ico 图标
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ExpenseHelper',
)
