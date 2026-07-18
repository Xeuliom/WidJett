# -*- mode: python ; coding: utf-8 -*-
# Widjett — single-file EXE spec (PyInstaller 6.x)

import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# ── Hidden imports required by PyQt5 + pynput + win32 + requests ─────────────
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
    # requests and its dependencies (needed for Prayer Times widget)
    'requests', 'requests.adapters', 'requests.auth', 'requests.cookies',
    'requests.exceptions', 'requests.models', 'requests.sessions',
    'certifi', 'urllib3', 'charset_normalizer', 'idna',
    # stdlib modules used by new widgets
    'calendar', 'json', 'uuid',
]

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('alarm.wav', '.'),
        ('logo.png',  '.'),
        ('widgets',   'widgets'),
    ],
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # GUI/Frameworks
        'tkinter', 'unittest', 'pydoc', 'doctest', 'difflib',
        'distutils', 'setuptools', 'pkg_resources',
        'IPython', 'notebook', 'jupyter', 'matplotlib', 'numpy', 'pandas', 'scipy', 'PIL',
        
        # Unused PyQt5 massive modules
        'PyQt5.QtNetwork', 'PyQt5.QtQml', 'PyQt5.QtSql', 'PyQt5.QtWebEngine', 
        'PyQt5.QtWebEngineCore', 'PyQt5.QtWebEngineWidgets', 'PyQt5.QtWebSockets', 
        'PyQt5.QtBluetooth', 'PyQt5.QtMultimedia', 'PyQt5.QtMultimediaWidgets', 
        'PyQt5.QtXml', 'PyQt5.QtTest', 'PyQt5.QtPrintSupport', 'PyQt5.QtDesigner', 
        'PyQt5.QtLocation', 'PyQt5.QtPositioning', 'PyQt5.QtSensors', 'PyQt5.QtNfc', 
        'PyQt5.QtTextToSpeech', 'PyQt5.QtDBus', 'PyQt5.QtOpenGL', 'PyQt5.QtQuick', 
        'PyQt5.QtQuickWidgets', 'PyQt5.QtSvg', 'PyQt5.QtScript', 'PyQt5.QtScriptTools'
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
