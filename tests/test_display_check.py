import math

import pytest

from checkerboard_fmri_task.display_check import screen_problems, stimulus_sizes


def test_stimulus_sizes_in_cm(config):
    sizes = {size.name: size for size in stimulus_sizes(config)}
    board = sizes["Checkerboard diameter"]
    assert board.deg == 16.0
    # Radius 8 degrees at 100 cm, on both sides of the centre.
    assert board.cm == pytest.approx(2 * math.tan(math.radians(8.0)) * 100)
    assert sizes["Fixation dot size"].cm == pytest.approx(math.tan(math.radians(0.5)) * 100)
    assert "Fixation line width" not in sizes


def test_matching_screen_has_no_problems(config):
    # 800 px over 40 cm = 20 px/cm: the 28 cm board is 562 px, inside 800 x 800.
    assert screen_problems(config, 800, 800, refresh_hz=60.0, scale=1.0) == []


def test_screen_problems_are_all_reported(config):
    problems = screen_problems(config, 1920, 1080, refresh_hz=75.0, scale=1.25)
    text = "\n".join(problems)
    assert "scaling is 125%" in text
    assert "config expects 60" in text
    assert "18.75 frames" in text  # 75 Hz / 4 reversals per second
    assert "cut off" in text  # 48 px/cm makes the board 1349 px, taller than 1080


def test_unknown_refresh_is_reported(config):
    problems = screen_problems(config, 800, 800, refresh_hz=None, scale=1.0)
    assert problems == ["Refresh rate not reported by Windows"]
