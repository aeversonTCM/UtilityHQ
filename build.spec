# -*- mode: python ; coding: utf-8 -*-
"""
UtilityHQ - PyInstaller Build Specification (onedir mode for fast builds)
Run: python -m PyInstaller build.spec --noconfirm
"""

import sys
from pathlib import Path

block_cipher = None

# Get the project root
PROJECT_ROOT = Path(SPECPATH)

a = Analysis(
    ['run.py'],
    pathex=[str(PROJECT_ROOT), str(PROJECT_ROOT / 'src')],
    binaries=[],
    datas=[
        # Include the src folder as a package
        ('src', 'src'),
        # Include resources
        ('resources', 'resources'),
    ],
    hiddenimports=[
        # PyQt6 modules
        'PyQt6.QtCore',
        'PyQt6.QtGui', 
        'PyQt6.QtWidgets',
        'PyQt6.QtCharts',
        # Database
        'sqlite3',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unnecessary modules to reduce size
        'tkinter',
        'matplotlib',
        'numpy.testing',
        'scipy',
        'PIL',
        'cv2',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# EXE without bundled data (for onedir mode)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='UtilityHQ',
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
    icon='resources/icon.ico' if Path('resources/icon.ico').exists() else None,
)

# COLLECT bundles everything into a folder
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='UtilityHQ',
)
