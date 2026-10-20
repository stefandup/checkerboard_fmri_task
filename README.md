# checkerboard_fmri_task

Fullscreen radial checkerboard (contrast-reversing, ON/OFF blocks, central fixation) for
fMRI, started by the scanner's Left Shift triggers. Built with Python + pyglet, shipped as a
standalone Windows program; the scanner PC needs no Python.

## Download for Windows

[![Download the Windows installer](https://img.shields.io/github/v/release/stefandup/checkerboard_fmri_task?label=Download%20for%20Windows&style=for-the-badge&logo=windows)](https://github.com/stefandup/checkerboard_fmri_task/releases/latest)

1. Click the button above (or go to the
   [latest release](https://github.com/stefandup/checkerboard_fmri_task/releases/latest)).
2. Under **Assets**, click the file named `CheckerboardFmriTaskSetup-v….exe` to download it.
3. Double-click the downloaded file and follow the installer. No Python or other software
   is needed.

If Windows shows "Windows protected your PC", click **More info**, then **Run anyway**. The
installer isn't code-signed, so Windows doesn't recognise it yet.

## Running a session

1. Check the values in `task_config.toml` (in the install folder; the installer adds a
   "config" desktop shortcut that opens it). It ships with basic working defaults: confirm
   them against your protocol and projector before collecting data.
2. Start **Checkerboard fMRI Task** from the desktop. In the console window, enter the
   participant ID and pick the screen (projector) if there is more than one.
3. The task measures the refresh rate (~2 s), then waits on a fixation screen. Start the
   scanner: the first `dummy_triggers` triggers are logged and discarded, the next one
   starts the task.
4. **Escape** aborts at any time. The log is saved either way.

Output goes to `Documents\checkerboard_fmri_task\`:

- `sub-<ID>_task-checkerboard_<date-time>_events.csv`: every trigger, block start,
  reversal, dropped frame and timing warning. `task_time_s` counts from the start trigger;
  `scheduled_task_time_s` is when the event should have happened.
- `..._config.toml`: an exact copy of the configuration used.

Command-line options (`checkerboard_fmri_task --help`): `--config`, `--participant`,
`--screen`, `--output-dir`, `--list-screens`, `--check-config`, `--check-display`.

`--check-display` lists every screen (refresh rate, resolution, Windows scaling), the
expected checkerboard and fixation sizes in degrees, cm and pixels, and anything that would
stop a screen showing the stimulus as configured. Run it on the scanner PC before a session.

## Development

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt -r requirements-dev.txt
.\.venv\Scripts\python -m pip install -e .
.\.venv\Scripts\python -m pytest
```

### Running from the venv

`pip install -e .` puts a `checkerboard_fmri_task` command in `.venv\Scripts\`. Activate the
venv to call it by name; it reads `config\task_config.toml` from the repo by default.

```powershell
.\.venv\Scripts\Activate.ps1
checkerboard_fmri_task --check-config   # validate the settings
checkerboard_fmri_task --list-screens
checkerboard_fmri_task                  # run a session
checkerboard_fmri_task --config config\test_config_UNVERIFIED.toml
```

Without activating: `.\.venv\Scripts\checkerboard_fmri_task.exe` or
`.\.venv\Scripts\python -m checkerboard_fmri_task.main`.

`config/test_config_UNVERIFIED.toml` holds best-guess values for trying the software out
only. Never collect data with it.

Code layout (`src/checkerboard_fmri_task/`): `config.py` (load/validate TOML),
`schedule.py` (blocks and reversal timing), `triggers.py`, `timing.py` (refresh and
dropped-frame checks), `event_log.py` (CSV), `checkerboard.py` (pattern geometry),
`runner.py` (session flow, tested with a fake display), `presentation.py` (the only pyglet
code) and `main.py` (CLI).

## Building

Needs [Inno Setup 6](https://jrsoftware.org/isinfo.php) for the installer. The exe and
installer icons are generated from `assets/Radial Checkerboard Optical Target.png` (via
Pillow, in `requirements-dev.txt`).

```powershell
.\build.ps1 -Full   # exe + installer
.\build.ps1 -Exe    # exe only: build_output\dist\checkerboard_fmri_task\
.\build.ps1 -Inno   # re-make the installer from the last exe build
```

The installer lands in `build_output\installer\`. It installs per user (no admin rights),
and adds desktop shortcuts. A reinstall first uninstalls the old version, then replaces
`task_config.toml` with the shipped defaults; the previous copy is saved next to it as
`task_config.previous.toml`.
Versions come from git tags (`git tag v1.0.0`).
