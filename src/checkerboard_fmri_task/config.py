"""Load and validate the task configuration (TOML)."""

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    """Raised when the configuration file is missing values or has invalid ones."""


@dataclass(frozen=True)
class ScannerConfig:
    trigger_key: str
    dummy_triggers: int


@dataclass(frozen=True)
class ParadigmConfig:
    first_block: str
    on_block_s: float
    off_block_s: float
    total_duration_s: float


@dataclass(frozen=True)
class StimulusConfig:
    reversal_rate_hz: float
    n_wedges: int
    n_rings: int
    inner_radius_deg: float
    outer_radius_deg: float
    ring_spacing: str
    contrast: float
    mean_luminance: float
    background_luminance: float

    @property
    def low_luminance(self) -> float:
        return self.mean_luminance * (1 - self.contrast)

    @property
    def high_luminance(self) -> float:
        return self.mean_luminance * (1 + self.contrast)


@dataclass(frozen=True)
class FixationConfig:
    shape: str
    size_deg: float
    color: tuple[float, float, float]
    line_width_deg: float | None


@dataclass(frozen=True)
class DisplayConfig:
    viewing_distance_cm: float
    screen_width_cm: float
    expected_refresh_hz: float | None
    dropped_frame_factor: float


@dataclass(frozen=True)
class TaskConfig:
    scanner: ScannerConfig
    paradigm: ParadigmConfig
    stimulus: StimulusConfig
    fixation: FixationConfig
    display: DisplayConfig


class _Section:
    """Reads one TOML table, collecting every problem instead of stopping at the first."""

    def __init__(self, data: dict[str, Any], name: str, problems: list[str]) -> None:
        self.name = name
        self.values: dict[str, Any] = data.get(name, {})
        self.problems = problems
        self.used: set[str] = set()

    def get(self, key: str, kind: type, required: bool = True) -> Any:
        self.used.add(key)
        try:
            value = self.values[key]
        except KeyError:
            if required:
                self.problems.append(f"[{self.name}] {key} is missing")
            return None
        if kind is float and isinstance(value, int) and not isinstance(value, bool):
            value = float(value)
        if not isinstance(value, kind) or (isinstance(value, bool) and kind is not bool):
            self.problems.append(f"[{self.name}] {key} must be {kind.__name__}, got {value!r}")
            return None
        return value

    def check_unknown_keys(self) -> None:
        for key in sorted(set(self.values) - self.used):
            self.problems.append(f"[{self.name}] {key} is not a known setting")


def load_config(path: Path) -> TaskConfig:
    try:
        with path.open("rb") as file:
            data = tomllib.load(file)
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{path} is not valid TOML: {e}") from e
    return parse_config(data)


def parse_config(data: dict[str, Any]) -> TaskConfig:
    problems: list[str] = []
    sections = ("scanner", "paradigm", "stimulus", "fixation", "display")
    for name in sorted(set(data) - set(sections)):
        problems.append(f"[{name}] is not a known section")

    scanner = _Section(data, "scanner", problems)
    paradigm = _Section(data, "paradigm", problems)
    stimulus = _Section(data, "stimulus", problems)
    fixation = _Section(data, "fixation", problems)
    display = _Section(data, "display", problems)

    values = {
        "scanner": {
            "trigger_key": scanner.get("trigger_key", str),
            "dummy_triggers": scanner.get("dummy_triggers", int),
        },
        "paradigm": {
            "first_block": paradigm.get("first_block", str),
            "on_block_s": paradigm.get("on_block_s", float),
            "off_block_s": paradigm.get("off_block_s", float),
            "total_duration_s": paradigm.get("total_duration_s", float),
        },
        "stimulus": {
            "reversal_rate_hz": stimulus.get("reversal_rate_hz", float),
            "n_wedges": stimulus.get("n_wedges", int),
            "n_rings": stimulus.get("n_rings", int),
            "inner_radius_deg": stimulus.get("inner_radius_deg", float),
            "outer_radius_deg": stimulus.get("outer_radius_deg", float),
            "ring_spacing": stimulus.get("ring_spacing", str),
            "contrast": stimulus.get("contrast", float),
            "mean_luminance": stimulus.get("mean_luminance", float),
            "background_luminance": stimulus.get("background_luminance", float),
        },
        "fixation": {
            "shape": fixation.get("shape", str),
            "size_deg": fixation.get("size_deg", float),
            "color": fixation.get("color", list),
            "line_width_deg": fixation.get(
                "line_width_deg", float, required=fixation.values.get("shape") == "cross"
            ),
        },
        "display": {
            "viewing_distance_cm": display.get("viewing_distance_cm", float),
            "screen_width_cm": display.get("screen_width_cm", float),
            "expected_refresh_hz": display.get("expected_refresh_hz", float, required=False),
            "dropped_frame_factor": display.get("dropped_frame_factor", float),
        },
    }
    for section in (scanner, paradigm, stimulus, fixation, display):
        section.check_unknown_keys()

    if not problems:
        problems.extend(_check_values(values))
    if problems:
        raise ConfigError("Configuration problems:\n  - " + "\n  - ".join(problems))

    fix = values["fixation"]
    fix["color"] = tuple(float(c) for c in fix["color"])
    return TaskConfig(
        scanner=ScannerConfig(**values["scanner"]),
        paradigm=ParadigmConfig(**values["paradigm"]),
        stimulus=StimulusConfig(**values["stimulus"]),
        fixation=FixationConfig(**fix),
        display=DisplayConfig(**values["display"]),
    )


def _check_values(values: dict[str, dict[str, Any]]) -> list[str]:
    problems: list[str] = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            problems.append(message)

    scanner, paradigm = values["scanner"], values["paradigm"]
    stimulus, fixation, display = values["stimulus"], values["fixation"], values["display"]

    require(scanner["trigger_key"] != "", "[scanner] trigger_key must not be empty")
    require(scanner["dummy_triggers"] >= 0, "[scanner] dummy_triggers must be 0 or more")

    require(
        paradigm["first_block"] in ("on", "off"), '[paradigm] first_block must be "on" or "off"'
    )
    for key in ("on_block_s", "off_block_s", "total_duration_s"):
        require(paradigm[key] > 0, f"[paradigm] {key} must be greater than 0")

    require(stimulus["reversal_rate_hz"] > 0, "[stimulus] reversal_rate_hz must be greater than 0")
    require(
        stimulus["n_wedges"] >= 2 and stimulus["n_wedges"] % 2 == 0,
        "[stimulus] n_wedges must be an even number, 2 or more",
    )
    require(stimulus["n_rings"] >= 1, "[stimulus] n_rings must be 1 or more")
    require(stimulus["inner_radius_deg"] >= 0, "[stimulus] inner_radius_deg must be 0 or more")
    require(
        stimulus["outer_radius_deg"] > stimulus["inner_radius_deg"],
        "[stimulus] outer_radius_deg must be larger than inner_radius_deg",
    )
    require(
        stimulus["ring_spacing"] in ("linear", "log"),
        '[stimulus] ring_spacing must be "linear" or "log"',
    )
    if stimulus["ring_spacing"] == "log":
        require(
            stimulus["inner_radius_deg"] > 0,
            '[stimulus] inner_radius_deg must be greater than 0 when ring_spacing is "log"',
        )
    require(0 <= stimulus["contrast"] <= 1, "[stimulus] contrast must be between 0 and 1")
    for key in ("mean_luminance", "background_luminance"):
        require(0 <= stimulus[key] <= 1, f"[stimulus] {key} must be between 0 and 1")
    require(
        stimulus["mean_luminance"] * (1 + stimulus["contrast"]) <= 1 + 1e-9,
        "[stimulus] mean_luminance * (1 + contrast) must not exceed 1 (white)",
    )

    require(fixation["shape"] in ("dot", "cross"), '[fixation] shape must be "dot" or "cross"')
    require(fixation["size_deg"] > 0, "[fixation] size_deg must be greater than 0")
    color = fixation["color"]
    require(
        len(color) == 3
        and all(isinstance(c, int | float) and not isinstance(c, bool) for c in color)
        and all(0 <= c <= 1 for c in color),
        "[fixation] color must be three numbers between 0 and 1",
    )
    if fixation["shape"] == "cross":
        require(
            0 < fixation["line_width_deg"] < fixation["size_deg"],
            "[fixation] line_width_deg must be greater than 0 and smaller than size_deg",
        )

    require(display["viewing_distance_cm"] > 0, "[display] viewing_distance_cm must be > 0")
    require(display["screen_width_cm"] > 0, "[display] screen_width_cm must be > 0")
    if display["expected_refresh_hz"] is not None:
        require(display["expected_refresh_hz"] > 0, "[display] expected_refresh_hz must be > 0")
    require(display["dropped_frame_factor"] > 1, "[display] dropped_frame_factor must be > 1")
    return problems
