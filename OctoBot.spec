# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build recipe for the Windows executable.

Build on Windows with the venv active:
    pip install pyinstaller
    pyinstaller --noconfirm OctoBot.spec
    # -> dist/OctoBot/OctoBot.exe  (onedir; keeps antivirus calm)

Windows version info (Properties > Details) is regenerated into
metadata.txt at build time from src/info.py; it is not committed.

Bundles:
  - src/translations  -> translations/   (resource_dir("translations"))
  - icons             -> icons/          (resource_dir("icons"))
  - neonize           -> the native Go runtime DLL (collect_all)
"""
import os
import runpy
import sys

from PyInstaller.utils.hooks import collect_all

SPECDIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SPECDIR)
gen_metadata = runpy.run_path(os.path.join(SPECDIR, "generateMetadata.py"))
METADATA_FILE = os.path.join(SPECDIR, "metadata.txt")
gen_metadata["generate_md"](METADATA_FILE)

info = runpy.run_path("src/info.py")
APP_NAME = info["app_name"]

neonize_datas, neonize_binaries, neonize_hiddenimports = collect_all("neonize")

a = Analysis(
    ["src/app.py"],
    pathex=["src"],
    binaries=neonize_binaries,
    datas=[
        ("src/translations", "translations"),
        ("icons", "icons"),
    ] + neonize_datas,
    hiddenimports=neonize_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    version=METADATA_FILE,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon="icons/favicon.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=APP_NAME,
)
