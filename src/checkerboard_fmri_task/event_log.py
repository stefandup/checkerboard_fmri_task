"""CSV event log, flushed after every row so aborted or crashed sessions keep their data."""

import csv
from pathlib import Path
from types import TracebackType

COLUMNS = (
    "time_s",
    "task_time_s",
    "scheduled_task_time_s",
    "event",
    "trigger_count",
    "block_index",
    "condition",
    "reversal_index",
    "frame",
    "detail",
)


def _number(value: float | None) -> str:
    return "" if value is None else f"{value:.6f}"


def _optional(value: object) -> str:
    return "" if value is None else str(value)


class EventLog:
    """time_s counts from session start; task_time_s from the start trigger."""

    def __init__(self, path: Path, session_start_s: float) -> None:
        self.path = path
        self.session_start_s = session_start_s
        self.task_start_s: float | None = None
        self._file = path.open("w", newline="", encoding="utf-8")
        self._writer = csv.writer(self._file)
        self._writer.writerow(COLUMNS)
        self._file.flush()

    def __enter__(self) -> "EventLog":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def write(
        self,
        time_s: float,
        event: str,
        *,
        scheduled_task_time_s: float | None = None,
        trigger_count: int | None = None,
        block_index: int | None = None,
        condition: str | None = None,
        reversal_index: int | None = None,
        frame: int | None = None,
        detail: str = "",
    ) -> None:
        task_time = None if self.task_start_s is None else time_s - self.task_start_s
        self._writer.writerow(
            (
                _number(time_s - self.session_start_s),
                _number(task_time),
                _number(scheduled_task_time_s),
                event,
                _optional(trigger_count),
                _optional(block_index),
                _optional(condition),
                _optional(reversal_index),
                _optional(frame),
                detail,
            )
        )
        self._file.flush()

    def close(self) -> None:
        self._file.close()
