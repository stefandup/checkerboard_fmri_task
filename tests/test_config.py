from pathlib import Path

import pytest

from checkerboard_fmri_task.config import ConfigError, load_config, parse_config

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_valid_config_parses(config_data):
    config = parse_config(config_data)
    assert config.scanner.dummy_triggers == 5
    assert config.paradigm.on_block_s == 10.0
    assert isinstance(config.paradigm.on_block_s, float)
    assert config.fixation.color == (1.0, 0.0, 0.0)
    assert config.fixation.line_width_deg is None


def test_black_and_white_luminances(config):
    assert config.stimulus.low_luminance == 0.0
    assert config.stimulus.high_luminance == 1.0


def test_shipped_config_is_valid_with_mean_grey_background():
    config = load_config(REPO_ROOT / "config" / "task_config.toml")
    assert config.stimulus.background_luminance == config.stimulus.mean_luminance == 0.5


def test_unverified_test_config_is_valid():
    config = load_config(REPO_ROOT / "config" / "test_config_UNVERIFIED.toml")
    assert config.scanner.dummy_triggers == 5


def test_all_missing_values_are_reported_together(config_data):
    del config_data["paradigm"]["on_block_s"]
    del config_data["stimulus"]["n_rings"]
    with pytest.raises(ConfigError) as error:
        parse_config(config_data)
    assert "[paradigm] on_block_s is missing" in str(error.value)
    assert "[stimulus] n_rings is missing" in str(error.value)


def test_unknown_keys_and_sections_are_rejected(config_data):
    config_data["stimulus"]["reversal_rate"] = 8
    config_data["extras"] = {}
    with pytest.raises(ConfigError) as error:
        parse_config(config_data)
    assert "[stimulus] reversal_rate is not a known setting" in str(error.value)
    assert "[extras] is not a known section" in str(error.value)


def test_wrong_type_is_rejected(config_data):
    config_data["stimulus"]["n_wedges"] = 8.5
    with pytest.raises(ConfigError, match="n_wedges must be int"):
        parse_config(config_data)


def test_bool_is_not_accepted_as_number(config_data):
    config_data["scanner"]["dummy_triggers"] = True
    with pytest.raises(ConfigError, match="dummy_triggers must be int"):
        parse_config(config_data)


@pytest.mark.parametrize(
    ("section", "key", "value", "message"),
    [
        ("scanner", "dummy_triggers", -1, "dummy_triggers must be 0 or more"),
        ("paradigm", "first_block", "rest", "first_block must be"),
        ("paradigm", "on_block_s", 0, "on_block_s must be greater than 0"),
        ("stimulus", "reversal_rate_hz", 0, "reversal_rate_hz must be greater than 0"),
        ("stimulus", "n_wedges", 7, "n_wedges must be an even number"),
        ("stimulus", "n_rings", 0, "n_rings must be 1 or more"),
        ("stimulus", "outer_radius_deg", 1.0, "outer_radius_deg must be larger"),
        ("stimulus", "ring_spacing", "cubic", "ring_spacing must be"),
        ("stimulus", "contrast", 1.5, "contrast must be between 0 and 1"),
        ("stimulus", "mean_luminance", 0.8, "must not exceed 1"),
        ("fixation", "shape", "star", "shape must be"),
        ("fixation", "color", [1.0, 0.0], "color must be three numbers"),
        ("display", "dropped_frame_factor", 1.0, "dropped_frame_factor must be > 1"),
    ],
)
def test_invalid_values_are_rejected(config_data, section, key, value, message):
    config_data[section][key] = value
    with pytest.raises(ConfigError, match=message):
        parse_config(config_data)


def test_log_spacing_needs_inner_radius(config_data):
    config_data["stimulus"]["ring_spacing"] = "log"
    config_data["stimulus"]["inner_radius_deg"] = 0.0
    with pytest.raises(ConfigError, match="inner_radius_deg must be greater than 0"):
        parse_config(config_data)


def test_cross_needs_line_width(config_data):
    config_data["fixation"]["shape"] = "cross"
    with pytest.raises(ConfigError, match=r"\[fixation\] line_width_deg is missing"):
        parse_config(config_data)
    config_data["fixation"]["line_width_deg"] = 0.1
    assert parse_config(config_data).fixation.line_width_deg == 0.1


def test_expected_refresh_is_optional(config_data):
    del config_data["display"]["expected_refresh_hz"]
    assert parse_config(config_data).display.expected_refresh_hz is None
