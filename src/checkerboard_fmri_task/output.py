"""Where session data goes, and checking it can actually be written there."""

import ctypes
import sys
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

APP_FOLDER = "checkerboard_fmri_task"
# Windows' "Documents" known folder; follows OneDrive and policy redirection, which
# Path.home() / "Documents" does not.
FOLDERID_DOCUMENTS = uuid.UUID("FDD39AD0-238F-46AF-ADB4-6C85480369C7")


def documents_dir() -> Path:
    if sys.platform == "win32":
        folder_id = ctypes.create_string_buffer(FOLDERID_DOCUMENTS.bytes_le, 16)
        path = ctypes.c_wchar_p()
        try:
            result = ctypes.windll.shell32.SHGetKnownFolderPath(
                folder_id, 0, None, ctypes.byref(path)
            )
            if result == 0 and path.value:
                return Path(path.value)
        finally:
            ctypes.windll.ole32.CoTaskMemFree(path)
    return Path.home() / "Documents"


def default_output_dir() -> Path:
    return documents_dir() / APP_FOLDER


def output_dir_problem(folder: Path) -> str | None:
    """Creates the folder and writes a throwaway file; returns why that failed, or None."""
    try:
        folder.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile(dir=folder) as file:
            file.write(b"write test")
    except OSError as e:
        return str(e)
    return None


def write_crash_report(text: str, folders: list[Path]) -> Path | None:
    """Saves text to the first folder that accepts it; None if none did."""
    name = f"crash_{datetime.now():%Y%m%d-%H%M%S}.txt"
    for folder in folders:
        try:
            folder.mkdir(parents=True, exist_ok=True)
            (folder / name).write_text(text, encoding="utf-8")
        except OSError:
            continue
        return folder / name
    return None
