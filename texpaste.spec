# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for TexPaste

import sys
from pathlib import Path

block_cipher = None

src_dir = Path('src')

a = Analysis(
    ['src/main.py'],
    pathex=[str(src_dir)],
    binaries=[],
    datas=[
        ('src/resources', 'resources'),
        ('config.default.json', '.'),
    ],
    hiddenimports=[
        'win32com.client',
        'win32com.server.util',
        'win32gui',
        'win32process',
        'win32event',
        'win32api',
        'pynput.keyboard._win32',
        'pynput.mouse._win32',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'psutil',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='TexPaste',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # No console window (tray app)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='src/resources/icons/texpaste.ico',
    onefile=True,
    version_file=None,
)
