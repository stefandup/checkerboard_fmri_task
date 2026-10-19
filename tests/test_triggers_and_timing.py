import pytest

from checkerboard_fmri_task.timing import (
    FrameMonitor,
    estimate_frame_interval,
    frames_per_reversal,
    is_whole_frames,
    refresh_matches,
)
from checkerboard_fmri_task.triggers import TriggerCounter


def test_dummy_triggers_then_start_then_volumes():
    counter = TriggerCounter(dummy_triggers=5)
    kinds = [counter.register(t * 2.0).kind for t in range(8)]
    assert kinds == ["dummy"] * 5 + ["start", "volume", "volume"]
    assert counter.start_time_s == 10.0


def test_zero_dummies_starts_on_first_trigger():
    counter = TriggerCounter(dummy_triggers=0)
    assert counter.register(1.0).kind == "start"
    assert counter.started


def test_trigger_intervals():
    counter = TriggerCounter(dummy_triggers=1)
    assert counter.register(1.0).interval_s is None
    assert counter.register(3.5).interval_s == pytest.approx(2.5)


def test_frame_interval_is_robust_to_one_slow_frame():
    flips = [i / 60 for i in range(10)] + [10 / 60 + 0.1]
    assert estimate_frame_interval(flips) == pytest.approx(1 / 60)


def test_frame_interval_needs_two_flips():
    with pytest.raises(ValueError):
        estimate_frame_interval([0.0])


@pytest.mark.parametrize(
    ("measured", "expected", "ok"), [(59.95, 60, True), (60.0, 60, True), (75.0, 60, False)]
)
def test_refresh_matches(measured, expected, ok):
    assert refresh_matches(measured, expected) is ok


@pytest.mark.parametrize(
    ("refresh", "rate", "whole"),
    [
        (60.0, 8.0, False),
        (60.0, 7.5, True),
        (60.0, 4.0, True),
        (120.0, 8.0, True),
        (60, 100, False),
    ],
)
def test_reversal_alignment_with_refresh(refresh, rate, whole):
    assert is_whole_frames(frames_per_reversal(refresh, rate)) is whole


def test_frame_monitor_flags_dropped_frames():
    monitor = FrameMonitor(frame_interval_s=0.01, dropped_frame_factor=1.5)
    assert monitor.record(0.00) is None
    assert monitor.record(0.01) is None
    assert monitor.record(0.03) == pytest.approx(0.02)
    assert monitor.record(0.04) is None
    assert monitor.frames == 4
    assert monitor.dropped == 1
    assert "dropped=1" in monitor.summary()
