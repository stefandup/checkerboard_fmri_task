"""Command-line entry point (also the PyInstaller entry script)."""

import ctypes
import logging
import platform
import re
import shutil
import sys
import tempfile
import time
import traceback
from collections import deque
from datetime import datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from types import TracebackType

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.markup import escape
from rich.table import Table
from rich.traceback import Traceback

from checkerboard_fmri_task.config import ConfigError, TaskConfig, load_config
from checkerboard_fmri_task.display_check import px_per_cm, screen_problems, stimulus_sizes
from checkerboard_fmri_task.event_log import EventLog
from checkerboard_fmri_task.graphics_check import (
    GRAPHICS_ADVICE,
    GraphicsError,
    display_adapters,
    graphics_problem,
    is_remote_session,
)
from checkerboard_fmri_task.output import (
    default_output_dir,
    output_dir_problem,
    write_crash_report,
)
from checkerboard_fmri_task.presentation import (
    PygletDisplay,
    list_screens,
    probe_opengl,
    trigger_symbol,
)
from checkerboard_fmri_task.runner import ABORT, FrameState, Session
from checkerboard_fmri_task.timing import estimate_frame_interval

console = Console()
logger = logging.getLogger("checkerboard_fmri_task")

FROZEN = getattr(sys, "frozen", False)
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


def _install_crash_handler(report_folders: list[Path]) -> None:
    """Unexpected errors: show the traceback, save it to a file, and keep the window open."""

    def handle(exc_type: type[BaseException], exc: BaseException, tb: TracebackType | None) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
            return
        console.print(Traceback.from_exception(exc_type, exc, tb))
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        report = write_crash_report(text, report_folders)
        if report is not None:
            console.print(f"[bold red]Unexpected error. Details saved to {escape(str(report))}[/]")
        if FROZEN:
            click.pause("Press any key to close...")

    sys.excepthook = handle


def _check_output_dir(output_dir: Path, config_path: Path) -> None:
    """Exits with advice if the output folder can't be written."""
    problem = output_dir_problem(output_dir)
    if problem is not None:
        _exit_with_error(
            f"Cannot save data to {output_dir}\n{problem}\n\n"
            "If Windows Security's 'Controlled folder access' is on, allow "
            "checkerboard_fmri_task.exe through it, or choose a folder outside Documents: "
            f"set [output] data_dir in {config_path}, or use --output-dir."
        )
    console.print(f"Output folder OK: [bold]{escape(str(output_dir))}[/]")


def _warn_graphics() -> None:
    """Early warning, before a participant is set up, that the window likely can't open."""
    problem = graphics_problem(display_adapters(), is_remote_session())
    if problem is not None:
        console.print(
            f"[bold yellow]Warning: {escape(problem)}. The task will probably not start.[/]\n"
            f"[yellow]{escape(GRAPHICS_ADVICE)}[/]"
        )


def _check_graphics() -> bool:
    """Opens a hidden OpenGL window and reports whether the task can draw on this PC."""
    try:
        info = probe_opengl()
    except GraphicsError as e:
        console.print(f"[bold red]Graphics: {escape(str(e))}[/]")
        hint = graphics_problem(display_adapters(), is_remote_session())
        if hint is not None:
            console.print(f"[yellow]Likely cause: {escape(hint)}[/]")
        console.print(f"[yellow]{escape(GRAPHICS_ADVICE)}[/]")
        return False
    console.print(
        f"Graphics: [bold green]OK[/] ({escape(info.renderer)}, "
        f"OpenGL {escape(info.version_string)})"
    )
    return True


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
    table = Table(
        "Index",
        "Monitor",
        "Primary",
        "Position",
        "Resolution",
        "Refresh (Hz)",
        "Scaling",
        title="Screens",
    )
    for s in list_screens():
        table.add_row(
            str(s.index),
            escape(s.name),
            "yes" if s.primary else "",
            f"({s.x}, {s.y})",
            f"{s.width} x {s.height}",
            "?" if s.refresh_hz is None else f"{s.refresh_hz:.2f}",
            f"{s.scale:.0%}",
        )
    console.print(table)


def _print_display_check(config: TaskConfig) -> None:
    screens = list_screens()
    _print_screens()
    disp = config.display
    table = Table(
        "Item",
        "Visual angle (deg)",
        "On screen (cm)",
        *(f"Screen {s.index} (px)" for s in screens),
        title=f"Expected stimulus size (viewing distance {disp.viewing_distance_cm} cm)",
    )
    for size in stimulus_sizes(config):
        table.add_row(
            size.name,
            f"{size.deg:.2f}",
            f"{size.cm:.2f}",
            *(f"{size.cm * px_per_cm(config, s.width, s.height):.0f}" for s in screens),
        )
    table.add_row(
        "Assumed image width",
        "",
        "",
        *(f"{disp.image_width_cm(s.width, s.height):.1f} cm" for s in screens),
    )
    console.print(table)
    source = (
        "screen_width_cm"
        if disp.screen_width_cm is not None
        else f"a {disp.screen_diagonal_inch}-inch diagonal"
    )
    console.print(
        f"Pixel sizes assume each screen's visible image width comes from {source}. "
        "Measure the checkerboard on the stimulus screen: it should match the cm column, "
        "horizontally and vertically."
    )
    for s in screens:
        problems = screen_problems(config, s.width, s.height, s.refresh_hz, s.scale)
        if not problems:
            console.print(f"Screen {s.index}: [bold green]OK[/]")
        for problem in problems:
            console.print(f"Screen {s.index}: [yellow]{escape(problem)}[/]")


def _print_config(config: TaskConfig) -> None:
    table = Table("Section", "Setting", "Value", title="Configuration")
    for section, values in vars(config).items():
        for name, value in vars(values).items():
            table.add_row(section, name, escape(str(value)))
    console.print(table)


def _show_static_checkerboard(config: TaskConfig, screen_index: int) -> None:
    """Fullscreen, non-reversing checkerboard until Escape; reports the measured refresh."""
    diameter = stimulus_sizes(config)[0]
    console.print(f"Showing the checkerboard on screen {screen_index}. Press Escape to close.")
    display = PygletDisplay(config, screen_index)
    for warning in display.warnings:
        console.print(f"[yellow]{escape(warning)}[/]")
    display.show_note(
        f"Checkerboard diameter should measure {diameter.cm:.2f} cm "
        f"({diameter.deg:.1f} deg), horizontally and vertically.   Esc closes."
    )
    frame = FrameState(show_checkerboard=True, inverted=False)
    flips: deque[float] = deque(maxlen=600)  # the last ~10 s at 60 Hz
    try:
        while not any(key.kind == ABORT for key in display.poll_keys()):
            display.draw(frame)
            flips.append(display.flip())
    finally:
        display.close()
    if len(flips) >= 2:
        console.print(f"Measured refresh: [bold]{1 / estimate_frame_interval(flips):.2f} Hz[/]")


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
@click.version_option(package_version(), prog_name="checkerboard_fmri_task")
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
    help="Folder for the event log [default: [output] data_dir, else Documents].",
)
@click.option("--list-screens", "show_screens", is_flag=True, help="List screens and exit.")
@click.option("--check-config", is_flag=True, help="Validate the configuration and exit.")
@click.option(
    "--check-graphics",
    is_flag=True,
    help="Check this PC's graphics can run the task, then exit (exit code 1 if not).",
)
@click.option(
    "--check-display",
    is_flag=True,
    help="Show each screen's refresh rate and the expected stimulus sizes, then exit.",
)
def main(
    config_path: Path,
    participant: str | None,
    screen_index: int | None,
    output_dir: Path | None,
    show_screens: bool,
    check_config: bool,
    check_graphics: bool,
    check_display: bool,
) -> None:
    """Radial checkerboard fMRI task. Escape aborts; the log is saved either way."""
    logging.basicConfig(
        level=logging.INFO, format="%(message)s", handlers=[RichHandler(console=console)]
    )
    _install_crash_handler([Path(tempfile.gettempdir())])
    console.print(f"[bold]Checkerboard fMRI Task v{escape(package_version())}[/]")
    if check_graphics:
        # No "press any key" pause: the installer runs this hidden and reads the exit code.
        raise SystemExit(0 if _check_graphics() else 1)
    _warn_graphics()
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
    console.print(f"Config: [bold]{escape(str(config_path.resolve()))}[/]")
    data_dir = output_dir or config.output.data_dir or default_output_dir()
    temp_dir = Path(tempfile.gettempdir())
    _install_crash_handler([data_dir, temp_dir])
    console.print(
        f"Crash reports go to: [bold]{escape(str(data_dir))}[/] "
        f"(or {escape(str(temp_dir))} if that folder can't be written)"
    )
    _print_config(config)
    if check_config:
        console.print("[bold green]Configuration OK[/]")
        _check_output_dir(data_dir, config_path)
        return
    if check_display:
        _print_display_check(config)
        if not _check_graphics():
            _exit_with_error("This PC can't show the checkerboard until the graphics are fixed.")
        if click.confirm("Show a static checkerboard to measure?", default=True):
            try:
                _show_static_checkerboard(config, _choose_screen(screen_index))
            except GraphicsError as e:
                _exit_with_error(f"{e}\n\n{GRAPHICS_ADVICE}")
        return

    while participant is None:
        answer = click.prompt("Participant ID")
        if PARTICIPANT_PATTERN.fullmatch(answer):
            participant = answer
        else:
            console.print("[red]Use letters and digits only.[/]")
    _check_output_dir(data_dir, config_path)
    screen = _choose_screen(screen_index)
    _raise_priority()
    try:
        run_task(config, config_path, participant, screen, data_dir)
    except GraphicsError as e:
        _exit_with_error(f"{e}\n\n{GRAPHICS_ADVICE}")
    if FROZEN:
        click.pause("Press any key to close...")


if __name__ == "__main__":
    main()
