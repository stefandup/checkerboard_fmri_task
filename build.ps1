#Requires -Version 7
param(
    [switch]$Full,
    [switch]$Exe,
    [switch]$Inno
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Every build artifact (PyInstaller's intermediate work files, its onedir output, the
# assembled installer payload, and the compiled installer itself) lives under this one
# gitignored root instead of separate top-level folders (build/, dist/, Output/).
$BuildOutput = Join-Path $PSScriptRoot "build_output"
$WorkPath = Join-Path $BuildOutput "work"
$DistPath = Join-Path $BuildOutput "dist"
$PayloadPath = Join-Path $BuildOutput "payload"
# checkerboard_fmri_task_installer.iss's OutputDir also points here. Tracked here too so
# Build-Installer can clear it before each compile -- installer filenames carry the version,
# so stale exes from older versions would otherwise pile up.
$InstallerPath = Join-Path $BuildOutput "installer"

# Resolved once, up front, rather than calling bare `pip`/`pyinstaller` and hoping PATH
# resolves both to the same interpreter -- otherwise `pip install -e .` can write fresh
# setuptools_scm version metadata into a *different* site-packages than the one PyInstaller
# reads it back from via `copy_metadata`, silently baking a stale version into the exe.
# Falls back to whatever `python` is on PATH if .venv doesn't exist yet (fresh clone).
$VenvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$Python = if (Test-Path $VenvPython) { $VenvPython } else { "python" }

# $ErrorActionPreference = "Stop" only turns *PowerShell* errors into terminating ones --
# it does nothing for a native command's exit code. Without this check, a failed
# `pip install`/`pyinstaller`/`ISCC.exe` call just prints its error and the script sails on.
function Assert-Success($What) {
    if ($LASTEXITCODE -ne 0) {
        throw "$What failed with exit code $LASTEXITCODE"
    }
}

function Show-Help {
    @"
Usage: .\build.ps1 -Full | -Exe | -Inno

  -Full   Build specs/checkerboard_fmri_task.spec, assemble
          build_output/payload/, then compile the installer.

  -Exe    Only build specs/checkerboard_fmri_task.spec from source into
          build_output/dist/checkerboard_fmri_task/. Skips assembling the
          payload and compiling the installer -- no Inno Setup needed.

  -Inno   Skip the PyInstaller build. Reuses build_output/dist/checkerboard_fmri_task/
          from a previous build, reassembles build_output/payload/, and
          (re)compiles checkerboard_fmri_task_installer.iss.

No option given: prints this help and exits without building anything.
"@ | Write-Host
}

function Build-Exes {
    & $Python -m pip install -e . --no-deps
    Assert-Success "pip install -e ."
    # --noconfirm: skip PyInstaller's interactive "output directory ... will be REMOVED!"
    # prompt -- this script has no stdin to answer it with.
    & $Python -m PyInstaller --noconfirm --workpath $WorkPath --distpath $DistPath `
        (Join-Path $PSScriptRoot "specs\checkerboard_fmri_task.spec")
    Assert-Success "PyInstaller build"
    # The exe looks for its config next to itself, where users can edit it.
    Copy-Item (Join-Path $PSScriptRoot "config\task_config.toml") `
        (Join-Path $DistPath "checkerboard_fmri_task")
}

function Build-Installer {
    # Read the version back from the venv's installed package metadata -- the exact same
    # source PyInstaller's copy_metadata baked into the exe -- rather than `git describe`.
    $version = "v" + (& $Python -c "from importlib.metadata import version; print(version('checkerboard-fmri-task'))").Trim()

    $bundleDir = Join-Path $DistPath "checkerboard_fmri_task"
    if (-not (Test-Path $bundleDir)) {
        throw "$bundleDir not found -- run '.\build.ps1 -Full' or '-Exe' first."
    }

    if (Test-Path $PayloadPath) { Remove-Item $PayloadPath -Recurse -Force }
    New-Item -ItemType Directory -Path $PayloadPath | Out-Null
    Copy-Item (Join-Path $bundleDir "*") $PayloadPath -Recurse

    if (Test-Path $InstallerPath) { Remove-Item $InstallerPath -Recurse -Force }

    $iscc = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    if (-not (Test-Path $iscc)) {
        $isccCmd = Get-Command ISCC.exe -ErrorAction SilentlyContinue
        if (-not $isccCmd) {
            throw "ISCC.exe (Inno Setup 6 compiler) not found. Install Inno Setup 6 or add ISCC.exe to PATH."
        }
        $iscc = $isccCmd.Source
    }

    & $iscc (Join-Path $PSScriptRoot "checkerboard_fmri_task_installer.iss") "/DMyAppVersion=$version"
    Assert-Success "ISCC.exe"
}

if ($Full) {
    Build-Exes
    Build-Installer
}
elseif ($Exe) {
    Build-Exes
}
elseif ($Inno) {
    Build-Installer
}
else {
    Show-Help
}
