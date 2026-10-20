"""Expected stimulus sizes and per-screen problems, for --check-display. No graphics library."""

from dataclasses import dataclass

from checkerboard_fmri_task.checkerboard import deg_to_px
from checkerboard_fmri_task.config import TaskConfig
from checkerboard_fmri_task.timing import frames_per_reversal, is_whole_frames, refresh_matches


@dataclass(frozen=True)
class StimulusSize:
    name: str
    deg: float  # visual angle
    cm: float  # physical size on the screen; measure it with a ruler to check the setup


def stimulus_sizes(config: TaskConfig) -> list[StimulusSize]:
    """Sizes as the display draws them (see PygletDisplay), in degrees and cm on screen."""
    stim, fix = config.stimulus, config.fixation
    distance = config.display.viewing_distance_cm

    def cm(deg: float) -> float:
        return deg_to_px(deg, distance, px_per_cm=1.0)

    sizes = [
        StimulusSize(
            "Checkerboard diameter", 2 * stim.outer_radius_deg, 2 * cm(stim.outer_radius_deg)
        ),
        StimulusSize(
            "Blank centre diameter", 2 * stim.inner_radius_deg, 2 * cm(stim.inner_radius_deg)
        ),
        StimulusSize(f"Fixation {fix.shape} size", fix.size_deg, cm(fix.size_deg)),
    ]
    if fix.line_width_deg is not None:
        sizes.append(
            StimulusSize("Fixation line width", fix.line_width_deg, cm(fix.line_width_deg))
        )
    return sizes


def px_per_cm(config: TaskConfig, width_px: int, height_px: int) -> float:
    return width_px / config.display.image_width_cm(width_px, height_px)


def screen_problems(
    config: TaskConfig,
    width_px: int,
    height_px: int,
    refresh_hz: float | None,
    scale: float,
) -> list[str]:
    """Reasons this screen would not show the stimulus as configured; empty if none."""
    problems = []
    if scale != 1.0:
        problems.append(
            f"Windows display scaling is {scale:.0%}: set it to 100% for this screen, "
            "or stimulus sizes may be wrong"
        )
    expected = config.display.expected_refresh_hz
    if refresh_hz is None:
        problems.append("Refresh rate not reported by Windows")
    else:
        if expected is not None and not refresh_matches(refresh_hz, expected):
            problems.append(f"Refresh {refresh_hz:.2f} Hz, config expects {expected} Hz")
        frames = frames_per_reversal(refresh_hz, config.stimulus.reversal_rate_hz)
        if not is_whole_frames(frames):
            problems.append(
                f"A reversal lasts {frames:.2f} frames at {refresh_hz:.2f} Hz, not a whole "
                "number: reversal timing will jitter by up to one frame"
            )
    outer_px = deg_to_px(
        config.stimulus.outer_radius_deg,
        config.display.viewing_distance_cm,
        px_per_cm(config, width_px, height_px),
    )
    if outer_px > min(width_px, height_px) / 2:
        problems.append(
            f"Checkerboard diameter {2 * outer_px:.0f} px does not fit on "
            f"{width_px}x{height_px}: its edge will be cut off"
        )
    return problems
