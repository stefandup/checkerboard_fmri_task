"""Session flow: measure refresh, wait for triggers, present blocks, log everything.

Talks to the screen only through the Display protocol, so it runs in tests with a fake display.
"""

import gc
import logging
from dataclasses import dataclass
from typing import NamedTuple, Protocol

from checkerboard_fmri_task.config import TaskConfig
from checkerboard_fmri_task.event_log import EventLog
from checkerboard_fmri_task.schedule import Schedule, StimulusState, build_blocks
from checkerboard_fmri_task.timing import (
    FrameMonitor,
    estimate_frame_interval,
    frames_per_reversal,
    is_whole_frames,
    refresh_matches,
)
from checkerboard_fmri_task.triggers import TriggerCounter

logger = logging.getLogger(__name__)

REFRESH_MEASUREMENT_FRAMES = 120
TRIGGER = "trigger"
ABORT = "abort"
COMPLETED = "completed"
ABORTED = "aborted"


class KeyPress(NamedTuple):
    kind: str  # TRIGGER or ABORT
    time_s: float


@dataclass(frozen=True)
class FrameState:
    show_checkerboard: bool
    inverted: bool
    # Set while waiting for the scanner: triggers left until the task starts. The display
    # then shows the waiting screen instead of the fixation.
    countdown: int | None = None


FIXATION_ONLY = FrameState(show_checkerboard=False, inverted=False)


class Display(Protocol):
    warnings: list[str]

    def describe(self) -> str: ...
    def poll_keys(self) -> list[KeyPress]: ...
    def draw(self, frame: FrameState) -> None: ...
    def flip(self) -> float: ...


class _Aborted(Exception):
    pass


class Session:
    def __init__(self, config: TaskConfig, display: Display, log: EventLog) -> None:
        self.config = config
        self.display = display
        self.log = log
        self.triggers = TriggerCounter(config.scanner.dummy_triggers)
        self.blocks = build_blocks(config.paradigm)
        self.schedule = Schedule(
            self.blocks, config.stimulus.reversal_rate_hz, config.paradigm.total_duration_s
        )
        self.last_flip_s = 0.0

    def run(self) -> str:
        try:
            self._log_setup()
            frame_interval_s = self._measure_refresh()
            self._wait_for_start()
            self._present(frame_interval_s)
        except _Aborted:
            return ABORTED
        return COMPLETED

    def _flip(self, frame: FrameState) -> float:
        self.display.draw(frame)
        self.last_flip_s = self.display.flip()
        return self.last_flip_s

    def _warn(self, time_s: float, message: str) -> None:
        logger.warning(message)
        self.log.write(time_s, "warning", detail=message)

    def _handle_keys(self) -> None:
        for key in self.display.poll_keys():
            if key.kind == ABORT:
                logger.warning("Aborted by operator")
                self.log.write(key.time_s, "abort", detail="escape pressed or window closed")
                raise _Aborted
            trigger = self.triggers.register(key.time_s)
            interval = (
                "" if trigger.interval_s is None else f"; interval_s={trigger.interval_s:.6f}"
            )
            if trigger.kind == "start":
                self.log.task_start_s = key.time_s
            self.log.write(
                key.time_s, "trigger", trigger_count=trigger.count, detail=trigger.kind + interval
            )
            logger.info(f"Trigger {trigger.count} ({trigger.kind})")
            if trigger.kind == "start":
                self.log.write(key.time_s, "task_start", trigger_count=trigger.count)

    def _waiting_frame(self) -> FrameState:
        return FrameState(False, False, countdown=self.triggers.remaining_until_start)

    def _log_setup(self) -> None:
        now = self._flip(self._waiting_frame())  # also gives the setup rows a real timestamp
        self.log.write(now, "display_info", detail=self.display.describe())
        for message in self.display.warnings:
            self._warn(now, message)
        last = self.blocks[-1]
        if last.truncated:
            self._warn(
                now,
                f"total_duration_s cuts the last block ({last.condition}) "
                f"to {last.duration_s:.3f} s",
            )

    def _measure_refresh(self) -> float:
        flips = []
        for _ in range(REFRESH_MEASUREMENT_FRAMES):
            self._handle_keys()
            flips.append(self._flip(self._waiting_frame()))
        if self.triggers.started:
            self._warn(
                flips[-1],
                "Start trigger arrived while the display was still measuring its refresh rate: "
                "the beginning of the task was not shown on time",
            )
        interval = estimate_frame_interval(flips)
        refresh_hz = 1 / interval
        self.log.write(flips[-1], "refresh_measured", detail=f"refresh_hz={refresh_hz:.3f}")
        logger.info(f"Measured refresh rate: {refresh_hz:.3f} Hz")

        expected = self.config.display.expected_refresh_hz
        if expected is not None and not refresh_matches(refresh_hz, expected):
            self._warn(flips[-1], f"Measured refresh {refresh_hz:.3f} Hz, expected {expected} Hz")
        frames = frames_per_reversal(refresh_hz, self.config.stimulus.reversal_rate_hz)
        if not is_whole_frames(frames):
            self._warn(
                flips[-1],
                f"A reversal lasts {frames:.3f} frames, not a whole number: reversal timing "
                "will jitter by up to one frame",
            )
        return interval

    def _wait_for_start(self) -> None:
        logger.info(
            f"Waiting for {self.config.scanner.dummy_triggers} dummy triggers + start trigger"
        )
        while True:
            self._handle_keys()
            if self.triggers.started:
                return
            self._flip(self._waiting_frame())

    def _present(self, frame_interval_s: float) -> None:
        task_start = self.log.task_start_s
        assert task_start is not None
        monitor = FrameMonitor(frame_interval_s, self.config.display.dropped_frame_factor)
        late_threshold_s = monitor.threshold_s
        previous: StimulusState | None = None
        frame = 0
        gc.disable()  # avoid garbage-collection pauses mid-run
        try:
            while True:
                self._handle_keys()
                # Choose the stimulus for when this frame will actually reach the screen.
                predicted = self.last_flip_s + frame_interval_s
                state = self.schedule.state_at(predicted - task_start)
                if state.finished:
                    break
                flip = self._flip(FrameState(state.condition == "on", state.inverted))
                frame += 1
                dropped = monitor.record(flip)
                if dropped is not None:
                    self.log.write(
                        flip,
                        "dropped_frame",
                        frame=frame,
                        detail=f"interval_ms={dropped * 1000:.3f}",
                    )
                self._log_changes(previous, state, flip, frame, late_threshold_s)
                previous = state
        finally:
            gc.enable()

        offset = self._flip(FIXATION_ONLY)
        self.log.write(
            offset,
            "task_end",
            scheduled_task_time_s=self.schedule.total_s,
            trigger_count=self.triggers.count,
        )
        self.log.write(offset, "frame_summary", detail=monitor.summary())
        logger.info(f"Task finished: {monitor.summary()}")

    def _log_changes(
        self,
        previous: StimulusState | None,
        state: StimulusState,
        flip: float,
        frame: int,
        late_threshold_s: float,
    ) -> None:
        scheduled_s = state.scheduled_s
        if previous is None or state.block_index != previous.block_index:
            event = "block_start"
            assert state.block_index is not None
            scheduled_s = self.blocks[state.block_index].onset_s
        elif state.reversal_index != previous.reversal_index:
            event = "reversal"
            assert state.reversal_index is not None and previous.reversal_index is not None
            skipped = state.reversal_index - previous.reversal_index - 1
            if skipped > 0:
                self._warn(flip, f"{skipped} reversal(s) never reached the screen (frame {frame})")
        else:
            return
        self.log.write(
            flip,
            event,
            scheduled_task_time_s=scheduled_s,
            block_index=state.block_index,
            condition=state.condition,
            reversal_index=state.reversal_index,
            frame=frame,
        )
        assert self.log.task_start_s is not None and scheduled_s is not None
        error_s = flip - self.log.task_start_s - scheduled_s
        if abs(error_s) > late_threshold_s:
            self._warn(flip, f"{event} at frame {frame} off schedule by {error_s * 1000:.3f} ms")
