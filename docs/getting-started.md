# Getting Started

This page covers installing the task and running a scan session. You don't need any coding
background.

## 1. Install it

[Download for Windows](https://github.com/stefandup/checkerboard_fmri_task/releases/latest){ .md-button .md-button--primary }

1. Click the button above. It opens the newest version's download page.
2. Under **Assets**, click the file named `CheckerboardFmriTaskSetup-v….exe` (for example
   `CheckerboardFmriTaskSetup-v0.1.1.exe`). Your browser downloads it.
3. Double-click the downloaded file and follow the steps.

The installer doesn't need admin rights. It adds two shortcuts to your desktop:

- **Checkerboard fMRI Task** starts the task.
- **Checkerboard fMRI Task config** opens the settings file, `task_config.toml`.

!!! warning "\"Windows protected your PC\""
    Windows may show this message the first time you run the installer. Click
    **More info**, then **Run anyway**. The installer isn't code-signed (bought from a
    certificate company), so Windows doesn't recognise it yet. It is the same file built
    from this project's code.

!!! note "Updating"
    To update, run a newer installer over the old one. It saves your old settings next to
    the new ones as `task_config.previous.toml`, so compare the two and copy across any
    values you changed.

## 2. Check the settings

Open the **Checkerboard fMRI Task config** desktop shortcut. It opens `task_config.toml`,
which holds the timing, the sizes and the number of start triggers to skip. The defaults work, but you should
check them against your scan protocol and your projector before collecting data.

## 3. Check the screen

Run the task's display check on the scanner PC before your first session. Open a
terminal (**Start** → type `PowerShell`), then copy and paste this line and press
**Enter**:

```powershell
& "$env:LOCALAPPDATA\Programs\CheckerboardFmriTask\checkerboard_fmri_task.exe" --check-display
```

It lists every screen with its refresh rate, resolution and Windows scaling. It also shows
the checkerboard and fixation sizes in degrees, cm and pixels, and warns you about
anything that would stop the stimulus showing correctly.

## 4. Run a session

1. Start **Checkerboard fMRI Task** from the desktop.
2. In the console window, type the participant ID. If the PC has more than one screen,
   pick the projector.
3. The task measures the screen's refresh rate (about 2 seconds), then shows the fixation
   dot and waits.
4. Start the scanner. The scanner sends a trigger (a Left Shift key press) with each
   volume. The first few triggers are skipped (`dummy_triggers` in the settings), and the
   next one starts the checkerboard.
5. Press **Escape** to stop early. The log is saved either way.

## 5. Find your output

Everything goes to the data folder chosen during install: by default
`Documents\checkerboard_fmri_task\`, opened by the **Checkerboard fMRI Task data** desktop
shortcut. To change it later, set `data_dir` under `[output]` in the settings file. The task
checks that it can save there right after you enter the participant ID.

If Windows Security's **Controlled folder access** is on, Windows may block saving to
Documents. Allow the program through it, or choose a folder outside Documents (for example
`D:/fmri_data`).

If something unexpected goes wrong, the window stays open with the error, and a
`crash_<date-time>.txt` file is saved in the data folder (the console shows where at launch). Send it to whoever
maintains the task.

The data folder holds:

- `sub-<ID>_task-checkerboard_<date-time>_events.csv` logs every trigger, block start,
  checkerboard flip, dropped frame and timing warning. `task_time_s` counts from the start
  trigger, and `scheduled_task_time_s` is when each event should have happened.
- `..._config.toml` is an exact copy of the settings used for that session.

## All options

Run the program with `--help` to see every option. Use the same line as in step 3, with
`--help` in place of `--check-display`.

| Option | What it does |
|---|---|
| `--config` | Use a different settings file. |
| `--participant` | Set the participant ID without being asked. |
| `--screen` | Pick the screen without being asked. |
| `--output-dir` | Save output somewhere else. |
| `--list-screens` | List the screens and stop. |
| `--check-config` | Check the settings file for mistakes and stop. |
| `--check-display` | Check the screens against the settings and stop (see step 3). |
| `--version` | Show the version and stop. The version is also printed at the top of every run. |
