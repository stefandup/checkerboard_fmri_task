"""Command-line entry point (also the PyInstaller entry script)."""

import ctypes
import logging
import platform
import re
import shutil
import sys
import time
from datetime import datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.markup import escape
from rich.table import Table

from checkerboard_fmri_task.config import ConfigError, TaskConfig, load_config
from checkerboard_fmri_task.event_log import EventLog
from checkerboard_fmri_task.presentation import PygletDisplay, list_screens, trigger_symbol
from checkerboard_fmri_task.runner import Session

console = Console()
logger = logging.getLogger("checkerboard_fmri_task")

FROZEN = getattr(sys, "frozen", False)
DEFAULT_OUTPUT_DIR = Path.home() / "Documents" / "checkerboard_fmri_task"
HIGH_PRIORITY_CLASS = 0x80
PARTICIPANT_PATTERN = re.compile(r"[A-Za-z0-9]+")


def default_config_path() -> Path:
    if FROZEN:
        return Path(sys.executable).parent / "task_config.toml"
    return Path(__file__).resolve().parents[2] / "config" / "task_config.toml"


def package_version() -> str:
    try:
        return version("checkerboard-fmri-task")
    except PackageNotFoundError:
        return "unknown"


def _validate_participant(
    ctx: click.Context, param: click.Parameter, value: str | None
) -> str | None:
    if value is not None and not PARTICIPANT_PATTERN.fullmatch(value):
        raise click.BadParameter("use letters and digits only")
    return value


def _exit_with_error(message: str) -> None:
    console.print(f"[bold red]{escape(message)}[/]")
    if FROZEN:
        click.pause("Press any key to close...")
    raise SystemExit(1)


def _raise_priority() -> None:
    if sys.platform == "win32":
        kernel32 = ctypes.windll.kernel32
        if not kernel32.SetPriorityClass(kernel32.GetCurrentProcess(), HIGH_PRIORITY_CLASS):
            logger.warning("Could not raise process priority")


def _choose_screen(screen_index: int | None) -> int:
    screens = list_screens()
    if screen_index is not None:
        if not 0 <= screen_index < len(screens):
            _exit_with_error(f"Screen {screen_index} does not exist (found {len(screens)})")
        return screen_index
    if len(screens) == 1:
        return 0
    _print_screens()
    return click.prompt(
        "Screen to present on", type=click.IntRange(0, len(screens) - 1), default=len(screens) - 1
    )


def _print_screens() -> None:
    table = Table("Index", "Position", "Resolution", title="Screens")
    for s in list_screens():
        table.add_row(str(s.index), f"({s.x}, {s.y})", f"{s.width} x {s.height}")
    console.print(table)


def _print_config(config: TaskConfig) -> None:
    table = Table("Section", "Setting", "Value", title="Configuration")
    for section, values in vars(config).items():
        for name, value in vars(values).items():
            table.add_row(section, name, escape(str(value)))
    console.print(table)


def run_task(
    config: TaskConfig, config_path: Path, participant: str, screen_index: int, output_dir: Path
) -> str:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    stem = f"sub-{participant}_task-checkerboard_{stamp}"
    events_path = output_dir / f"{stem}_events.csv"
    # Exact config used, saved next to the log, for reproducibility.
    shutil.copy2(config_path, output_dir / f"{stem}_config.toml")

    session_start = time.perf_counter()
    status = "incomplete"
    with EventLog(events_path, session_start) as log:
        log.write(
            session_start,
            "session_start",
            detail=(
                f"participant={participant}; wall_clock={datetime.now().isoformat()}; "
                f"task_version={package_version()}; python={platform.python_version()}; "
                f"os={platform.platform()}; config={config_path}"
            ),
        )
        display = PygletDisplay(config, screen_index)
        try:
            status = Session(config, display, log).run()
        finally:
            log.write(time.perf_counter(), "session_end", detail=f"status={status}")
            display.close()
            console.print(f"Log saved: [bold]{events_path}[/] (status: {status})")
    return status


@click.command()
@click.option(
    "--config",
    "config_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=default_config_path,
    show_default="task_config.toml",
    help="Task configuration file.",
)
@click.option(
    "--participant", callback=_validate_participant, help="Participant ID (letters/digits)."
)
@click.option("--screen", "screen_index", type=int, help="Screen index to present on.")
@click.option(
    "--output-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=DEFAULT_OUTPUT_DIR,
    show_default=True,
    help="Folder for the event log.",
)
@click.option("--list-screens", "show_screens", is_flag=True, help="List screens and exit.")
@click.option("--check-config", is_flag=True, help="Validate the configuration and exit.")
def main(
    config_path: Path,
    participant: str | None,
    screen_index: int | None,
    output_dir: Path,
    show_screens: bool,
    check_config: bool,
) -> None:
    """Radial checkerboard fMRI task. Escape aborts; the log is saved either way."""
    logging.basicConfig(
        level=logging.INFO, format="%(message)s", handlers=[RichHandler(console=console)]
    )
    if show_screens:
        _print_screens()
        return
    try:
        config = load_config(config_path)
        trigger_symbol(config.scanner.trigger_key)
    except FileNotFoundError:
        _exit_with_error(f"Config file not found: {config_path}")
        return
    except ConfigError as e:
        _exit_with_error(f"{config_path}\n{e}")
        return
    if check_config:
        _print_config(config)
        console.print("[bold green]Configuration OK[/]")
        return

    while participant is None:
        answer = click.prompt("Participant ID")
        if PARTICIPANT_PATTERN.fullmatch(answer):
            participant = answer
        else:
            console.print("[red]Use letters and digits only.[/]")
    screen = _choose_screen(screen_index)
    _raise_priority()
    run_task(config, config_path, participant, screen, output_dir)
    if FROZEN:
        click.pause("Press any key to close...")


if __name__ == "__main__":
    main()
