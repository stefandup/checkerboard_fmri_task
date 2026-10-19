import copy
from typing import Any

import pytest

from checkerboard_fmri_task.config import TaskConfig, parse_config

# Arbitrary values that make the arithmetic in tests easy to follow. Not a recommendation.
VALID_CONFIG: dict[str, Any] = {
    "scanner": {"trigger_key": "LSHIFT", "dummy_triggers": 5},
    "paradigm": {"first_block": "off", "on_block_s": 10, "off_block_s": 10, "total_duration_s": 40},
    "stimulus": {
        "reversal_rate_hz": 4.0,
        "n_wedges": 8,
        "n_rings": 4,
        "inner_radius_deg": 1.0,
        "outer_radius_deg": 8.0,
        "ring_spacing": "linear",
        "contrast": 1.0,
        "mean_luminance": 0.5,
        "background_luminance": 0.5,
    },
    "fixation": {"shape": "dot", "size_deg": 0.5, "color": [1.0, 0.0, 0.0]},
    "display": {
        "viewing_distance_cm": 100,
        "screen_width_cm": 40,
        "expected_refresh_hz": 60,
        "dropped_frame_factor": 1.5,
    },
}


@pytest.fixture
def config_data() -> dict[str, Any]:
    return copy.deepcopy(VALID_CONFIG)


@pytest.fixture
def config(config_data: dict[str, Any]) -> TaskConfig:
    return parse_config(config_data)
