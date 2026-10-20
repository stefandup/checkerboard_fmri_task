"""Spots PCs that can't give pyglet a hardware OpenGL 3.3 context. No graphics library."""

import ctypes
import sys
from ctypes import wintypes

# Windows' stand-in adapters: OpenGL 1.1 in software only, too old for pyglet.
FALLBACK_ADAPTERS = (
    "microsoft basic display",
    "microsoft basic render",
    "microsoft remote display",
)
DISPLAY_DEVICE_MIRRORING_DRIVER = 0x8
SM_REMOTESESSION = 0x1000
MIN_OPENGL = (3, 3)  # pyglet 2 draws with shaders

GRAPHICS_ADVICE = (
    "Install the graphics driver for this PC: Windows Update > Advanced options > Optional "
    "updates > Driver updates, the PC maker's support page, or the Intel/NVIDIA/AMD driver "
    "tool (needs admin rights, so you may need IT). Run the task at the PC itself, not over "
    "Remote Desktop. Device Manager > Display adapters shows the installed driver. If the "
    "driver is already the newest one, the graphics chip is too old for this task (roughly "
    "pre-2013, e.g. Intel HD Graphics 2000/3000): use another PC."
)


class GraphicsError(Exception):
    """No usable OpenGL: the window can't be created."""


class _DisplayDevice(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("DeviceName", wintypes.WCHAR * 32),
        ("DeviceString", wintypes.WCHAR * 128),
        ("StateFlags", wintypes.DWORD),
        ("DeviceID", wintypes.WCHAR * 128),
        ("DeviceKey", wintypes.WCHAR * 128),
    ]


def display_adapters() -> list[str]:
    """Names of the display adapters Windows knows about; empty off Windows."""
    if sys.platform != "win32":
        return []
    names = []
    device = _DisplayDevice(cb=ctypes.sizeof(_DisplayDevice))
    i = 0
    while ctypes.windll.user32.EnumDisplayDevicesW(None, i, ctypes.byref(device), 0):
        # Mirroring drivers are screen-capture helpers, not adapters that draw.
        if not device.StateFlags & DISPLAY_DEVICE_MIRRORING_DRIVER:
            names.append(device.DeviceString)
        i += 1
    return list(dict.fromkeys(names))  # one entry per adapter, not per output


def is_remote_session() -> bool:
    return sys.platform == "win32" and bool(ctypes.windll.user32.GetSystemMetrics(SM_REMOTESESSION))


def opengl_problem(version: tuple[int, int]) -> str | None:
    """Why the OpenGL version the driver gave is too old; None if it's new enough."""
    if version < MIN_OPENGL:
        major, minor = MIN_OPENGL
        return f"OpenGL {version[0]}.{version[1]} is too old: the task needs {major}.{minor}"
    return None


def graphics_problem(adapters: list[str], remote_session: bool) -> str | None:
    """Why this PC likely can't run the task's graphics; None if nothing obvious."""
    if remote_session:
        return "Running over Remote Desktop, which usually only offers OpenGL 1.1"
    if adapters and all(name.lower().startswith(FALLBACK_ADAPTERS) for name in adapters):
        return f"No graphics driver installed (only {', '.join(adapters)})"
    return None
