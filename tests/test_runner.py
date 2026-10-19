"""End-to-end session runs against a simulated 60 Hz display with scripted triggers."""

import csv
from pathlib import Path

import pytest

from checkerboard_fmri_task.event_log import EventLog
from checkerboard_fmri_task.runner import (
    ABORT,
    ABORTED,
    COMPLETED,
    REFRESH_MEASUREMENT_FRAMES,
    TRIGGER,
    FrameState,
    KeyPress,
    Session,
)

FRAME_S = 1 / 60
TR_S = 2.0


class FakeDisplay:
    """Flips exactly every FRAME_S; the scanner sends a trigger every TR_S from first_trigger_s."""

    def __init__(self, first_trigger_s=3.0, abort_at_s=None, slow_frames=()):
        self.now = 0.0
        self.next_trigger_s = first_trigger_s
        self.abort_at_s = abort_at_s
        self.slow_frames = set(slow_frames)
        self.flips = 0
        self.drawn: list[tuple[float, FrameState]] = []
        self.warnings: list[str] = []

    def describe(self) -> str:
        return "fake display"

    def poll_keys(self) -> list[KeyPress]:
        keys = []
        while self.next_trigger_s <= self.now:
            keys.append(KeyPress(TRIGGER, self.next_trigger_s))
            self.next_trigger_s += TR_S
        if self.abort_at_s is not None and self.now >= self.abort_at_s:
            keys.append(KeyPress(ABORT, self.now))
        return keys

    def draw(self, frame: FrameState) -> None:
        self.pending = frame

    def flip(self) -> float:
        self.flips += 1
        self.now += FRAME_S * (3 if self.flips in self.slow_frames else 1)
        self.drawn.append((self.now, self.pending))
        return self.now


def run(config, tmp_path: Path, display: FakeDisplay) -> tuple[str, list[dict[str, str]]]:
    path = tmp_path / "events.csv"
    with EventLog(path, session_start_s=0.0) as log:
        status = Session(config, display, log).run()
    with path.open(newline="") as file:
        return status, list(csv.DictReader(file))


def events(rows, name):
    return [row for row in rows if row["event"] == name]


def test_full_session(config, tmp_path):
    status, rows = run(config, tmp_path, FakeDisplay(first_trigger_s=3.0))
    assert status == COMPLETED
    assert all(float(row["time_s"]) >= 0 for row in rows)

    triggers = events(rows, "trigger")
    assert [t["detail"].split(";")[0] for t in triggers[:6]] == ["dummy"] * 5 + ["start"]
    start = events(rows, "task_start")[0]
    assert float(start["time_s"]) == pytest.approx(3.0 + 5 * TR_S)
    assert float(start["task_time_s"]) == 0.0

    blocks = events(rows, "block_start")
    assert [b["condition"] for b in blocks] == ["off", "on", "off", "on"]
    for block, onset in zip(blocks, (0.0, 10.0, 20.0, 30.0), strict=True):
        assert float(block["scheduled_task_time_s"]) == onset
        # Shown on the first frame at or after the scheduled time.
        # (+1e-5 allows for the CSV's 6-decimal rounding.)
        assert 0 <= float(block["task_time_s"]) - onset < FRAME_S + 1e-5

    # 2 ON blocks x 10 s x 4 reversals/s, minus the block_start rows that open them.
    assert len(events(rows, "reversal")) == 2 * 10 * 4 - 2
    end = events(rows, "task_end")[0]
    assert 40.0 <= float(end["task_time_s"]) < 40.0 + 2 * FRAME_S
    assert events(rows, "dropped_frame") == []
    assert events(rows, "warning") == []


def test_display_follows_schedule(config, tmp_path):
    display = FakeDisplay(first_trigger_s=0.5)
    run(config, tmp_path, display)
    task_start = 0.5 + 5 * TR_S
    for time_s, frame in display.drawn:
        t = time_s - task_start
        if 0.001 < t < 9.999:
            assert not frame.show_checkerboard
        if 10.001 < t < 19.999:
            assert frame.show_checkerboard
            reversals = (t - 10.0) * 4
            if abs(reversals - round(reversals)) > 1e-6:  # skip frames exactly on a boundary
                assert frame.inverted == (int(reversals) % 2 == 1)


def test_triggers_before_measurement_finishes_are_counted(config, tmp_path):
    status, rows = run(config, tmp_path, FakeDisplay(first_trigger_s=0.0))
    assert status == COMPLETED
    assert len(events(rows, "trigger")) >= 6
    assert events(rows, "warning") == []


def test_start_trigger_during_refresh_measurement_is_warned(config_data, tmp_path):
    from checkerboard_fmri_task.config import parse_config

    config_data["scanner"]["dummy_triggers"] = 0
    _, rows = run(parse_config(config_data), tmp_path, FakeDisplay(first_trigger_s=0.5))
    warnings = [w["detail"] for w in events(rows, "warning")]
    assert any("still measuring its refresh rate" in w for w in warnings)
    # The first block is reported as late against its own onset, not a later reversal.
    first_block = events(rows, "block_start")[0]
    assert float(first_block["scheduled_task_time_s"]) == 0.0
    assert any("block_start at frame 1 off schedule" in w for w in warnings)


def test_abort_while_waiting_is_logged(config, tmp_path):
    status, rows = run(config, tmp_path, FakeDisplay(first_trigger_s=100.0, abort_at_s=5.0))
    assert status == ABORTED
    assert rows[-1]["event"] == "abort"
    assert events(rows, "task_start") == []


def test_abort_mid_task_keeps_log(config, tmp_path):
    status, rows = run(config, tmp_path, FakeDisplay(first_trigger_s=1.0, abort_at_s=25.0))
    assert status == ABORTED
    assert rows[-1]["event"] == "abort"
    assert len(events(rows, "block_start")) == 2


def test_dropped_frames_are_logged(config, tmp_path):
    slow = REFRESH_MEASUREMENT_FRAMES + 1000
    status, rows = run(config, tmp_path, FakeDisplay(first_trigger_s=0.5, slow_frames=[slow]))
    assert status == COMPLETED
    dropped = events(rows, "dropped_frame")
    assert len(dropped) == 1
    assert "interval_ms=50.000" in dropped[0]["detail"]
    assert "dropped=1" in events(rows, "frame_summary")[0]["detail"]


def test_reversal_rate_not_matching_refresh_is_warned(config_data, tmp_path):
    from checkerboard_fmri_task.config import parse_config

    config_data["stimulus"]["reversal_rate_hz"] = 7.0
    _, rows = run(parse_config(config_data), tmp_path, FakeDisplay())
    assert any("not a whole number" in w["detail"] for w in events(rows, "warning"))


def test_refresh_mismatch_is_warned(config_data, tmp_path):
    from checkerboard_fmri_task.config import parse_config

    config_data["display"]["expected_refresh_hz"] = 75
    _, rows = run(parse_config(config_data), tmp_path, FakeDisplay())
    assert any("expected 75" in w["detail"] for w in events(rows, "warning"))


def test_log_is_readable_without_close(tmp_path):
    path = tmp_path / "events.csv"
    log = EventLog(path, session_start_s=1.0)
    log.write(3.5, "trigger", trigger_count=1)
    with path.open(newline="") as file:
        rows = list(csv.DictReader(file))
    assert rows[0]["time_s"] == "2.500000"
    assert rows[0]["task_time_s"] == ""
    log.close()
