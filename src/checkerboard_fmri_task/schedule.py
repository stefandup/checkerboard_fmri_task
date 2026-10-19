"""ON/OFF block schedule and contrast-reversal timing. Pure logic, no graphics."""

import math
from bisect import bisect_right
from dataclasses import dataclass

from checkerboard_fmri_task.config import ParadigmConfig

# Guards against floating-point error at exact block/reversal boundaries.
EPSILON_S = 1e-9


@dataclass(frozen=True)
class Block:
    index: int
    condition: str
    onset_s: float
    duration_s: float
    truncated: bool


@dataclass(frozen=True)
class StimulusState:
    finished: bool
    block_index: int | None = None
    condition: str | None = None
    reversal_index: int | None = None
    scheduled_s: float | None = None

    @property
    def inverted(self) -> bool:
        return self.reversal_index is not None and self.reversal_index % 2 == 1


def build_blocks(paradigm: ParadigmConfig) -> list[Block]:
    durations = {"on": paradigm.on_block_s, "off": paradigm.off_block_s}
    total = paradigm.total_duration_s
    blocks: list[Block] = []
    counts = {"on": 0, "off": 0}
    condition = paradigm.first_block
    while True:
        # Onsets from block counts rather than a running sum, so error never accumulates.
        onset = counts["on"] * durations["on"] + counts["off"] * durations["off"]
        if onset >= total - EPSILON_S:
            return blocks
        planned = durations[condition]
        duration = min(planned, total - onset)
        blocks.append(
            Block(len(blocks), condition, onset, duration, duration < planned - EPSILON_S)
        )
        counts[condition] += 1
        condition = "off" if condition == "on" else "on"


class Schedule:
    def __init__(self, blocks: list[Block], reversal_rate_hz: float, total_s: float) -> None:
        self.blocks = blocks
        self.reversal_rate_hz = reversal_rate_hz
        self.total_s = total_s
        self._onsets = [block.onset_s for block in blocks]

    def state_at(self, task_time_s: float) -> StimulusState:
        """What should be on screen at a task time (seconds since the start trigger)."""
        t = max(task_time_s, 0.0)
        if t >= self.total_s - EPSILON_S:
            return StimulusState(finished=True)
        block = self.blocks[bisect_right(self._onsets, t + EPSILON_S) - 1]
        if block.condition == "off":
            return StimulusState(False, block.index, "off", None, block.onset_s)
        reversal_index = math.floor((t - block.onset_s) * self.reversal_rate_hz + EPSILON_S)
        scheduled = block.onset_s + reversal_index / self.reversal_rate_hz
        return StimulusState(False, block.index, "on", reversal_index, scheduled)
