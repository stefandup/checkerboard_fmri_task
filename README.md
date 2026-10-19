# checkerboard_fmri_task

Fullscreen radial checkerboard (contrast-reversing, ON/OFF blocks, central fixation) for
fMRI, started by the scanner's Left Shift triggers. Built with Python + pyglet, shipped as a
standalone Windows program; the scanner PC needs no Python.

## Running a session

1. Fill in every `REQUIRED` value in `task_config.toml` (in the install folder; the
   installer adds a "config" desktop shortcut that opens it). The task refuses to start
   until they're set.
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
`--screen`, `--output-dir`, `--list-screens`, `--check-config`.

## Development

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt -r requirements-dev.txt
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python src\checkerboard_fmri_task\main.py --config config\test_config_UNVERIFIED.toml
```

`config/test_config_UNVERIFIED.toml` holds best-guess values for trying the software out
only. Never collect data with it.

Code layout (`src/checkerboard_fmri_task/`): `config.py` (load/validate TOML),
`schedule.py` (blocks and reversal timing), `triggers.py`, `timing.py` (refresh and
dropped-frame checks), `event_log.py` (CSV), `checkerboard.py` (pattern geometry),
`runner.py` (session flow, tested with a fake display), `presentation.py` (the only pyglet
code) and `main.py` (CLI).

## Building

Needs [Inno Setup 6](https://jrsoftware.org/isinfo.php) for the installer.

```powershell
.\build.ps1 -Full   # exe + installer
.\build.ps1 -Exe    # exe only: build_output\dist\checkerboard_fmri_task\
.\build.ps1 -Inno   # re-make the installer from the last exe build
```

The installer lands in `build_output\installer\`. It installs per user (no admin rights),
adds desktop shortcuts, and never overwrites or removes an edited `task_config.toml`.
Versions come from git tags (`git tag v1.0.0`).
