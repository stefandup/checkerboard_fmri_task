# -*- mode: python ; coding: utf-8 -*-
# Builds every tool as one onedir bundle so they share a single copy of their
# dependencies instead of each tool carrying its own full copy.
import os

from PyInstaller.utils.hooks import collect_submodules, copy_metadata

REPO_ROOT = os.path.join(SPECPATH, "..")
SRC_ROOT = os.path.join(REPO_ROOT, "src", "checkerboard_fmri_task")
# Generated from assets/ by build.ps1 before PyInstaller runs.
ICON_PATH = os.path.join(REPO_ROOT, "build_output", "checkerboard_fmri_task.ico")

# (exe_name, script path relative to src/checkerboard_fmri_task, console window?, extra datas)
TOOLS = [
    ("checkerboard_fmri_task", "main.py", True, []),
]

collect_args = []

for name, script, console, extra_datas in TOOLS:
    a = Analysis(
        [os.path.join(SRC_ROOT, script)],
        pathex=[os.path.join(REPO_ROOT, "src")],
        binaries=[],
        datas=[*extra_datas, *copy_metadata("checkerboard-fmri-task")],
        # pyglet picks its platform backends at runtime, so PyInstaller can't see them.
        hiddenimports=collect_submodules("pyglet"),
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
        name=name,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        console=console,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=ICON_PATH,
    )
    collect_args.extend([exe, a.binaries, a.zipfiles, a.datas])

# A single COLLECT for every tool: identical dependency files (same
# destination path) are only written to disk once.
COLLECT(
    *collect_args,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="checkerboard_fmri_task",
)
