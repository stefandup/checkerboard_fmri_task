"""Frame-timing checks: refresh-rate estimate and dropped-frame detection."""

import statistics
from collections.abc import Sequence

# Measured refresh may differ from the expected one by this fraction before it's a warning.
REFRESH_TOLERANCE = 0.02
# A reversal period may be off a whole number of frames by this fraction of a frame.
FRAME_ALIGNMENT_TOLERANCE = 0.05


def estimate_frame_interval(flip_times_s: Sequence[float]) -> float:
    """Median interval between consecutive flips (robust to the odd slow frame)."""
    if len(flip_times_s) < 2:
        raise ValueError("Need at least two flip times to estimate the frame interval")
    intervals = [b - a for a, b in zip(flip_times_s, flip_times_s[1:], strict=False)]
    return statistics.median(intervals)


def refresh_matches(measured_hz: float, expected_hz: float) -> bool:
    return abs(measured_hz - expected_hz) <= expected_hz * REFRESH_TOLERANCE


def frames_per_reversal(refresh_hz: float, reversal_rate_hz: float) -> float:
    return refresh_hz / reversal_rate_hz


def is_whole_frames(frames: float) -> bool:
    return abs(frames - round(frames)) <= FRAME_ALIGNMENT_TOLERANCE and round(frames) >= 1


class FrameMonitor:
    def __init__(self, frame_interval_s: float, dropped_frame_factor: float) -> None:
        self.frame_interval_s = frame_interval_s
        self.threshold_s = frame_interval_s * dropped_frame_factor
        self.frames = 0
        self.dropped = 0
        self.max_interval_s = 0.0
        self._last_flip_s: float | None = None

    def record(self, flip_time_s: float) -> float | None:
        """Register a flip; return its interval if it counts as a dropped frame."""
        self.frames += 1
        last, self._last_flip_s = self._last_flip_s, flip_time_s
        if last is None:
            return None
        interval = flip_time_s - last
        self.max_interval_s = max(self.max_interval_s, interval)
        if interval > self.threshold_s:
            self.dropped += 1
            return interval
        return None

    def summary(self) -> str:
        return (
            f"frames={self.frames}; dropped={self.dropped}; "
            f"max_interval_ms={self.max_interval_s * 1000:.3f}; "
            f"expected_interval_ms={self.frame_interval_s * 1000:.3f}"
        )
