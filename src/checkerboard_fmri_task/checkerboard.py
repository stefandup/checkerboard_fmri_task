"""Radial checkerboard geometry. Pure numpy, no graphics library."""

import math

import numpy as np

OUTSIDE = -1


def deg_to_px(deg: float, viewing_distance_cm: float, px_per_cm: float) -> float:
    """Eccentricity in degrees of visual angle to a distance in pixels from screen centre."""
    return math.tan(math.radians(deg)) * viewing_distance_cm * px_per_cm


def radial_checkerboard(
    outer_radius_px: float,
    inner_radius_px: float,
    n_wedges: int,
    n_rings: int,
    ring_spacing: str,
) -> np.ndarray:
    """Square int array: 0/1 for the two check colours, OUTSIDE beyond the annulus."""
    size = math.ceil(outer_radius_px) * 2
    coords = np.arange(size) - (size - 1) / 2
    x, y = np.meshgrid(coords, -coords)
    radius = np.hypot(x, y)
    angle = np.mod(np.arctan2(y, x), 2 * np.pi)

    wedge = np.floor(angle / (2 * np.pi / n_wedges)).astype(int)
    if ring_spacing == "log":
        position = np.log(np.maximum(radius, inner_radius_px) / inner_radius_px) / np.log(
            outer_radius_px / inner_radius_px
        )
    else:
        position = (radius - inner_radius_px) / (outer_radius_px - inner_radius_px)
    ring = np.floor(position * n_rings).astype(int)

    pattern = (wedge + ring) % 2
    pattern[(radius < inner_radius_px) | (radius >= outer_radius_px)] = OUTSIDE
    return pattern


def render_rgba(pattern: np.ndarray, low: float, high: float, inverted: bool) -> np.ndarray:
    """Pattern to an RGBA uint8 image; OUTSIDE pixels are fully transparent."""
    first, second = (high, low) if inverted else (low, high)
    grey = np.where(pattern == 1, second, first)
    rgba = np.zeros((*pattern.shape, 4), dtype=np.uint8)
    rgba[..., :3] = np.round(grey * 255).astype(np.uint8)[..., None]
    rgba[..., 3] = np.where(pattern == OUTSIDE, 0, 255)
    return rgba
