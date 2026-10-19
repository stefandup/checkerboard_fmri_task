"""Scanner trigger counting, including dummy acquisitions."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Trigger:
    count: int
    kind: str  # "dummy", "start" or "volume"
    time_s: float
    interval_s: float | None


class TriggerCounter:
    def __init__(self, dummy_triggers: int) -> None:
        self.dummy_triggers = dummy_triggers
        self.count = 0
        self.start_time_s: float | None = None
        self._last_time_s: float | None = None

    @property
    def started(self) -> bool:
        return self.start_time_s is not None

    def register(self, time_s: float) -> Trigger:
        self.count += 1
        interval = None if self._last_time_s is None else time_s - self._last_time_s
        self._last_time_s = time_s
        if self.count <= self.dummy_triggers:
            kind = "dummy"
        elif self.count == self.dummy_triggers + 1:
            kind = "start"
            self.start_time_s = time_s
        else:
            kind = "volume"
        return Trigger(self.count, kind, time_s, interval)
