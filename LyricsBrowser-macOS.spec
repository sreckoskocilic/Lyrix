# -*- mode: python ; coding: utf-8 -*-
# Build on macOS:
#   pip install pyinstaller PySide6 lyricsgenius python-dotenv
#   pyinstaller LyricsBrowser-macOS.spec
#
# To code-sign (optional, required for Gatekeeper without quarantine):
#   Set CODESIGN_IDENTITY to your "Developer ID Application: ..." identity,
#   or leave None to skip signing (app will need to be approved via System Settings
#   > Privacy & Security the first time it's opened).
#
# Produces:  dist/LyricsBrowser.app

import os

from PyInstaller.utils.hooks import collect_all, collect_submodules

CODESIGN_IDENTITY = None  # e.g. "Developer ID Application: Jane Doe (XXXXXXXXXX)"

icon_file = "LyricsBrowser.icns"

# The QML files and the vendored Roboto Mono faces are read at runtime from
# lyrix/ui; theme.package_dir() resolves them under sys._MEIPASS in the bundle.
datas = [
    ("lyrix/ui/qml", "lyrix/ui/qml"),
    ("lyrix/ui/fonts", "lyrix/ui/fonts"),
]
if os.path.exists(".env"):
    datas.append((".env", "."))
if os.path.exists(icon_file):
    datas.append((icon_file, "."))

lg_d, lg_b, lg_h = collect_all("lyricsgenius")
dot_d, dot_b, dot_h = collect_all("dotenv")

# PySide6's hook brings the Qt libraries, plugins and QML modules for the imported
# PySide6 submodules.
a = Analysis(
    ["run.py"],
    pathex=["."],
    binaries=lg_b + dot_b,
    datas=datas + lg_d + dot_d,
    hiddenimports=lg_h + dot_h + collect_submodules("lyricsgenius"),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Qt subsystems Lyrix does not import. Each one drags in tens of megabytes of
        # frameworks, and PySide6's hook only skips what nothing imports.
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineQuick",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtMultimedia",
        "PySide6.QtMultimediaWidgets",
        "PySide6.QtCharts",
        "PySide6.QtDataVisualization",
        "PySide6.QtGraphs",
        "PySide6.Qt3DCore",
        "PySide6.Qt3DRender",
        "PySide6.Qt3DInput",
        "PySide6.Qt3DLogic",
        "PySide6.Qt3DAnimation",
        "PySide6.Qt3DExtras",
        "PySide6.QtPdf",
        "PySide6.QtPdfWidgets",
        "PySide6.QtBluetooth",
        "PySide6.QtNfc",
        "PySide6.QtPositioning",
        "PySide6.QtSerialPort",
        "PySide6.QtSql",
        "PySide6.QtTest",
        # toolkits and packages Lyrix no longer uses; keeps a dirty venv from leaking in
        "tkinter",
        "ttkbootstrap",
        "pyglet",
        "PIL",
        "PyQt5",
        "PyQt6",
        "PySide2",
        "matplotlib",
        "IPython",
        "pytest",
        # optional mypyc-compiled speedup — pure Python fallback is used when absent
        "charset_normalizer.md__mypyc",
    ],
    noarchive=False,
    optimize=1,
)
# The PySide6 hook collects Qt wholesale: QtWebEngineCore alone is 217 MB, and nothing in
# Lyrix imports it. `excludes` only drops the Python wrapper modules, not the frameworks,
# the QML modules or the resources behind them, so filter the collected files by name.
QT_DROP = (
    "QtWebEngine",
    "QtPdf",
    "Qt3D",
    "QtQuick3D",
    "QtGraphs",
    "QtDataVisualization",
    "QtCharts",
    "QtMultimedia",
    "QtSpatialAudio",
    "QtSql",
    "QtTest",
    "QtDesigner",
    "QtHelp",
    "QtUiTools",
    "QtBluetooth",
    "QtNfc",
    "QtPositioning",
    "QtLocation",
    "QtSerialPort",
    "QtSerialBus",
    "QtWebSockets",
    "QtWebChannel",
    "QtWebView",
    "QtRemoteObjects",
    "QtScxml",
    "QtSensors",
    "QtTextToSpeech",
    "QtVirtualKeyboard",
)


def _keep(entry):
    return not any(name in entry[0] for name in QT_DROP)


a.binaries = [e for e in a.binaries if _keep(e)]
a.datas = [e for e in a.datas if _keep(e)]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LyricsBrowser",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX is unreliable on macOS arm64/universal2
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,  # None = native arch; use "universal2" for fat binary
    codesign_identity=CODESIGN_IDENTITY,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="LyricsBrowser",
)

app = BUNDLE(
    coll,
    name="LyricsBrowser.app",
    icon=icon_file if os.path.exists(icon_file) else None,
    bundle_identifier="com.lyrix.lyricsbrowser",
    info_plist={
        "CFBundleName": "LyricsBrowser",
        "CFBundleDisplayName": "Lyrics Browser",
        "CFBundleShortVersionString": "1.6.0",
        "CFBundleVersion": "1",
        "NSHighResolutionCapable": True,
        "NSRequiresAquaSystemAppearance": False,  # allows dark mode
        "NSAppleEventsUsageDescription": "Lyrics Browser uses Apple Events for file dialogs.",
        "NSPrincipalClass": "NSApplication",
    },
)
