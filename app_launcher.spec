# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, copy_metadata


project_dir = Path(SPECPATH)

datas = []
binaries = []
hiddenimports = [
    "scripts",
    "scripts.serial_excel_logger",
    "scripts.serial_logger_with_plot",
    "scripts.serial_raw_excel_logger",
    "scripts.extract_reliable_data",
    "video_meter_to_excel",
]

package_datas, package_binaries, package_hiddenimports = collect_all("rapidocr_onnxruntime")
datas += package_datas
binaries += package_binaries
hiddenimports += package_hiddenimports

datas += copy_metadata("openpyxl")
datas += copy_metadata("rapidocr_onnxruntime")
datas += copy_metadata("onnxruntime")


a = Analysis(
    ["app_launcher.py"],
    pathex=[str(project_dir)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    [],
    exclude_binaries=True,
    name="实验软件",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="实验软件",
)
