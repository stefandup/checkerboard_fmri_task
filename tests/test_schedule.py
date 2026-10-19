import pytest

from checkerboard_fmri_task.config import ParadigmConfig
from checkerboard_fmri_task.schedule import Schedule, build_blocks


def paradigm(first="off", on=10.0, off=10.0, total=40.0) -> ParadigmConfig:
    return ParadigmConfig(first_block=first, on_block_s=on, off_block_s=off, total_duration_s=total)


def test_blocks_alternate_starting_with_first_block():
    blocks = build_blocks(paradigm(first="off"))
    assert [b.condition for b in blocks] == ["off", "on", "off", "on"]
    assert [b.onset_s for b in blocks] == [0.0, 10.0, 20.0, 30.0]
    assert not any(b.truncated for b in blocks)


def test_unequal_block_durations():
    blocks = build_blocks(paradigm(first="on", on=12.0, off=18.0, total=60.0))
    assert [(b.condition, b.onset_s, b.duration_s) for b in blocks] == [
        ("on", 0.0, 12.0),
        ("off", 12.0, 18.0),
        ("on", 30.0, 12.0),
        ("off", 42.0, 18.0),
    ]


def test_last_block_is_truncated_at_total_duration():
    blocks = build_blocks(paradigm(total=35.0))
    assert blocks[-1].duration_s == 5.0
    assert blocks[-1].truncated


def test_onsets_do_not_accumulate_float_error():
    blocks = build_blocks(paradigm(on=0.1, off=0.2, total=300.0))
    assert blocks[-1].onset_s == pytest.approx(299.9, abs=1e-9)


def make_schedule(rate=4.0, **kwargs) -> Schedule:
    p = paradigm(**kwargs)
    return Schedule(build_blocks(p), rate, p.total_duration_s)


def test_off_block_shows_no_checkerboard():
    state = make_schedule().state_at(5.0)
    assert state.condition == "off"
    assert state.reversal_index is None
    assert not state.inverted


@pytest.mark.parametrize(
    ("t", "reversal_index", "scheduled"),
    [
        (10.0, 0, 10.0),
        (10.2, 0, 10.0),
        (10.25, 1, 10.25),
        (10.5, 2, 10.5),
        (10.74, 2, 10.5),
        (19.99, 39, 19.75),
    ],
)
def test_reversals_at_rate_from_block_onset(t, reversal_index, scheduled):
    state = make_schedule(rate=4.0).state_at(t)
    assert state.condition == "on"
    assert state.reversal_index == reversal_index
    assert state.scheduled_s == pytest.approx(scheduled)
    assert state.inverted == (reversal_index % 2 == 1)


def test_reversal_count_restarts_each_on_block():
    schedule = make_schedule()
    assert schedule.state_at(30.0).block_index == 3
    assert schedule.state_at(30.0).reversal_index == 0


def test_exact_boundaries_survive_float_error():
    # 0.1 * 3 == 0.30000000000000004 and 0.7 * 10 rounds just under 7 in some forms
    schedule = make_schedule(rate=10.0)
    assert schedule.state_at(10.0 + 0.7).reversal_index == 7
    assert schedule.state_at(10.3).reversal_index == 3


def test_finished_at_total_duration():
    schedule = make_schedule()
    assert schedule.state_at(39.999).finished is False
    assert schedule.state_at(40.0).finished is True


def test_negative_time_is_clamped_to_start():
    state = make_schedule().state_at(-0.01)
    assert state.block_index == 0
