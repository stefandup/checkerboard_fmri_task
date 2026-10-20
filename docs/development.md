# Development & Building

This page is for changing the code. If you only want to run scans, see
[Getting Started](getting-started.md).

## Set up

You need Python 3.13. A **virtual environment** ("venv") is a private folder of Python
packages for this project only, so it can't clash with anything else on your PC.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt -r requirements-dev.txt
.\.venv\Scripts\python -m pip install -e .
.\.venv\Scripts\python -m pytest
```

The last line runs the tests. If they all pass, you're set up.

## Run from the venv

`pip install -e .` adds a `checkerboard_fmri_task` command to `.venv\Scripts\`. Activate
the venv to use it by name. It reads `config\task_config.toml` from the repo by default.

```powershell
.\.venv\Scripts\Activate.ps1
checkerboard_fmri_task --check-config   # check the settings
checkerboard_fmri_task --list-screens
checkerboard_fmri_task                  # run a session
checkerboard_fmri_task --config config\test_config_UNVERIFIED.toml
```

!!! warning
    `config/test_config_UNVERIFIED.toml` holds best-guess values for trying the software
    out. Never collect data with it.

## Where the code lives

Everything is in `src/checkerboard_fmri_task/`:

| File | What it does |
|---|---|
| `config.py` | Loads and checks the TOML settings. |
| `schedule.py` | Works out the blocks and flip timing. |
| `triggers.py` | Handles the scanner triggers. |
| `timing.py` | Measures the refresh rate and spots dropped frames. |
| `event_log.py` | Writes the CSV log. |
| `checkerboard.py` | Draws the checkerboard pattern. |
| `runner.py` | Runs a session. Tested with a fake display. |
| `presentation.py` | The only code that uses pyglet (the graphics library). |
| `main.py` | The command line. |

!!! note "Going further"
    Keeping all pyglet code in `presentation.py` means everything else can be tested
    without opening a window. `runner.py` takes the display as an input, so the tests can
    pass in a fake one.

## Build the installer

You need [Inno Setup 6](https://jrsoftware.org/isinfo.php) to build the installer.

```powershell
.\build.ps1 -Full   # exe + installer
.\build.ps1 -Exe    # exe only: build_output\dist\checkerboard_fmri_task\
.\build.ps1 -Inno   # re-make the installer from the last exe build
```

The installer lands in `build_output\installer\`.

## Release a new version

The version number comes from git tags. Pushing a tag that starts with `v` makes GitHub
build the installer and attach it to a new release.

```powershell
git tag -a v0.2.0 -m "What changed"
git push origin v0.2.0
gh run watch          # follow the build
```

The download buttons always point at the newest release, so you don't need to change them.

## Preview these docs

```powershell
.\.venv\Scripts\mkdocs serve
```

Then open <http://127.0.0.1:8000>. Read `docrules.md` before writing a page.
