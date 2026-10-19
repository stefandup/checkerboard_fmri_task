import math

import numpy as np
import pytest

from checkerboard_fmri_task.checkerboard import OUTSIDE, deg_to_px, radial_checkerboard, render_rgba


def test_deg_to_px():
    # 45 degrees at 50 cm is 50 cm from centre; at 10 px/cm that is 500 px.
    assert deg_to_px(45.0, 50.0, 10.0) == pytest.approx(500.0)
    assert deg_to_px(0.0, 50.0, 10.0) == 0.0


def test_pattern_shape_and_annulus():
    pattern = radial_checkerboard(100.0, 20.0, n_wedges=8, n_rings=4, ring_spacing="linear")
    assert pattern.shape == (200, 200)
    assert pattern[100, 100] == OUTSIDE  # centre hole
    assert pattern[0, 0] == OUTSIDE  # corner, beyond the outer radius
    assert set(np.unique(pattern)) == {OUTSIDE, 0, 1}


def pixel_at(pattern: np.ndarray, radius: float, angle_deg: float) -> int:
    centre = (pattern.shape[0] - 1) / 2
    x = centre + radius * math.cos(math.radians(angle_deg))
    y = centre - radius * math.sin(math.radians(angle_deg))
    return int(pattern[round(y), round(x)])


def test_neighbouring_wedges_and_rings_alternate():
    pattern = radial_checkerboard(200.0, 0.0, n_wedges=4, n_rings=2, ring_spacing="linear")
    # Wedges are 90 degrees; rings split at radius 100.
    assert pixel_at(pattern, 50, 45) != pixel_at(pattern, 50, 135)
    assert pixel_at(pattern, 50, 45) != pixel_at(pattern, 150, 45)
    assert pixel_at(pattern, 50, 45) == pixel_at(pattern, 150, 135)


def test_log_rings_widen_with_eccentricity():
    pattern = radial_checkerboard(160.0, 10.0, n_wedges=2, n_rings=4, ring_spacing="log")
    # Log spacing from 10 to 160 px puts ring edges at 20, 40, 80 px.
    assert pixel_at(pattern, 15, 45) != pixel_at(pattern, 25, 45)
    assert pixel_at(pattern, 25, 45) == pixel_at(pattern, 35, 45)
    assert pixel_at(pattern, 45, 45) == pixel_at(pattern, 75, 45)
    assert pixel_at(pattern, 75, 45) != pixel_at(pattern, 85, 45)


def test_inverted_image_swaps_check_colours():
    pattern = radial_checkerboard(50.0, 5.0, n_wedges=8, n_rings=3, ring_spacing="linear")
    normal = render_rgba(pattern, 0.0, 1.0, inverted=False)
    inverted = render_rgba(pattern, 0.0, 1.0, inverted=True)
    inside = pattern != OUTSIDE
    assert np.all(normal[inside, 0].astype(int) + inverted[inside, 0] == 255)
    assert np.all(normal[~inside, 3] == 0)
    assert np.all(normal[inside, 3] == 255)
