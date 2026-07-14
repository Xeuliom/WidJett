# -*- mode: python ; coding: utf-8 -*-
# Widjett — single-file EXE spec (PyInstaller 6.x)

import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# ── Hidden imports required by PyQt5 + pynput + win32 ────────────────────────
hidden = [
    'winreg',
    'win32api', 'win32con', 'win32gui', 'win32process', 'win32clipboard',
    'pynput', 'pynput.keyboard', 'pynput.mouse',
    'pynput.keyboard._win32', 'pynput.mouse._win32',
    'watchdog', 'watchdog.observers', 'watchdog.observers.winapi',
    'watchdog.events',
    'psutil',
    'PyQt5', 'PyQt5.QtCore', 'PyQt5.QtGui', 'PyQt5.QtWidgets',
    'PyQt5.sip',
]

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('alarm.wav', '.'),
        ('logo.png',  '.'),
    ],
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'unittest', 'email', 'html', 'http',
        'urllib', 'xml', 'pydoc', 'doctest', 'difflib',
        'distutils', 'setuptools', 'pkg_resources',
    ],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='widjett',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,               # no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='logo.png',
    # Windows version info shown in Properties → Details
    version=None,
)
