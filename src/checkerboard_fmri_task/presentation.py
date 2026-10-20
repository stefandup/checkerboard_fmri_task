"""pyglet window: draws FrameStates and timestamps flips and key presses."""

import time
from dataclasses import dataclass

import pyglet
from pyglet import gl
from pyglet.window import key

from checkerboard_fmri_task.checkerboard import deg_to_px, radial_checkerboard, render_rgba
from checkerboard_fmri_task.config import ConfigError, TaskConfig
from checkerboard_fmri_task.runner import ABORT, TRIGGER, FrameState, KeyPress


@dataclass(frozen=True)
class ScreenInfo:
    index: int
    x: int
    y: int
    width: int
    height: int


def list_screens() -> list[ScreenInfo]:
    screens = pyglet.display.get_display().get_screens()
    return [ScreenInfo(i, s.x, s.y, s.width, s.height) for i, s in enumerate(screens)]


def trigger_symbol(key_name: str) -> int:
    try:
        return getattr(key, key_name)
    except AttributeError as e:
        raise ConfigError(f"[scanner] trigger_key {key_name!r} is not a pyglet key name") from e


def _to_texture(rgba) -> pyglet.image.Texture:
    height, width = rgba.shape[:2]
    # Negative pitch: numpy rows run top-to-bottom, OpenGL rows bottom-to-top.
    image = pyglet.image.ImageData(width, height, "RGBA", rgba.tobytes(), pitch=-width * 4)
    return image.get_texture()


def _rgb255(color: tuple[float, float, float]) -> tuple[int, int, int, int]:
    r, g, b = (round(c * 255) for c in color)
    return r, g, b, 255


class PygletDisplay:
    def __init__(self, config: TaskConfig, screen_index: int) -> None:
        self._trigger = trigger_symbol(config.scanner.trigger_key)
        screen = pyglet.display.get_display().get_screens()[screen_index]
        self.window = pyglet.window.Window(
            fullscreen=True, screen=screen, vsync=True, caption="checkerboard_fmri_task"
        )
        self.window.set_mouse_visible(False)
        self.window.push_handlers(on_key_press=self._on_key_press, on_close=self._on_close)
        self._keys: list[KeyPress] = []
        self.warnings: list[str] = []

        stim, disp = config.stimulus, config.display
        bg = stim.background_luminance
        gl.glClearColor(bg, bg, bg, 1.0)

        self._px_per_cm = screen.width / disp.screen_width_cm
        self._px_per_deg_centre = deg_to_px(1.0, disp.viewing_distance_cm, self._px_per_cm)
        outer_px = deg_to_px(stim.outer_radius_deg, disp.viewing_distance_cm, self._px_per_cm)
        inner_px = deg_to_px(stim.inner_radius_deg, disp.viewing_distance_cm, self._px_per_cm)
        self._outer_px = outer_px
        pattern = radial_checkerboard(
            outer_px, inner_px, stim.n_wedges, stim.n_rings, stim.ring_spacing
        )
        low, high = stim.low_luminance, stim.high_luminance
        self._textures = (
            _to_texture(render_rgba(pattern, low, high, bg, inverted=False)),
            _to_texture(render_rgba(pattern, low, high, bg, inverted=True)),
        )
        self._centre = (self.window.width / 2, self.window.height / 2)
        self._origin = (
            self._centre[0] - pattern.shape[1] / 2,
            self._centre[1] - pattern.shape[0] / 2,
        )

        self._batch = pyglet.graphics.Batch()
        self._fixation = self._make_fixation(config, disp.viewing_distance_cm)
        self._waiting_batch = pyglet.graphics.Batch()
        self._countdown_label = self._make_waiting_screen(bg, config.fixation.shape)
        self._warm_up()

        if outer_px > min(screen.width, screen.height) / 2:
            self.warnings.append(
                f"Checkerboard radius {outer_px:.0f} px is larger than half the screen "
                f"({screen.width}x{screen.height}): its edge will be cut off"
            )
        framebuffer = self.window.get_framebuffer_size()
        if tuple(framebuffer) != (screen.width, screen.height):
            self.warnings.append(
                f"Framebuffer {framebuffer} differs from screen {screen.width}x{screen.height} "
                "(Windows display scaling?): stimulus sizes will be wrong"
            )
        self._screen = screen

    def _make_fixation(self, config: TaskConfig, distance_cm: float) -> list:
        fix = config.fixation
        cx, cy = self._centre
        size = deg_to_px(fix.size_deg, distance_cm, self._px_per_cm)
        color = _rgb255(fix.color)
        if fix.shape == "dot":
            return [pyglet.shapes.Circle(cx, cy, size / 2, color=color, batch=self._batch)]
        assert fix.line_width_deg is not None
        width = deg_to_px(fix.line_width_deg, distance_cm, self._px_per_cm)
        return [
            pyglet.shapes.Rectangle(
                cx - size / 2, cy - width / 2, size, width, color=color, batch=self._batch
            ),
            pyglet.shapes.Rectangle(
                cx - width / 2, cy - size / 2, width, size, color=color, batch=self._batch
            ),
        ]

    def _make_waiting_screen(self, background: float, fixation_shape: str) -> pyglet.text.Label:
        """Instructions, waiting message and countdown, top to bottom; returns the countdown.

        Text is white or black, whichever contrasts with the background.
        """
        cx, cy = self._centre
        size = self.window.height / 30
        color = (255, 255, 255, 255) if background < 0.5 else (0, 0, 0, 255)
        style = {"anchor_x": "center", "anchor_y": "center", "color": color}
        # (text, font scale, space below in multiples of size); None marks the countdown.
        lines = [
            (f"Keep your eyes on the {fixation_shape} in the centre.", 1.0, 2.0),
            ("Please lie as still as possible.", 1.0, 2.0),
            ("A flickering pattern will come and go.", 1.0, 5.0),
            ("Waiting for scanner to start", 1.2, 3.5),
            (None, 2.5, 0.0),
        ]
        y = cy + sum(gap for _, _, gap in lines) * size / 2
        self._waiting_labels: list[pyglet.text.Label] = []
        for text, scale, gap in lines:
            label = pyglet.text.Label(
                text or "", font_size=size * scale, x=cx, y=y, batch=self._waiting_batch, **style
            )
            self._waiting_labels.append(label)
            y -= gap * size
        return self._waiting_labels[-1]

    def _warm_up(self) -> None:
        """Draw everything once, off-screen, so the first ON block doesn't stall on GPU setup."""
        for texture in self._textures:
            texture.blit(*self._origin)
        self._batch.draw()
        self._waiting_batch.draw()
        gl.glFinish()
        self.window.clear()

    def _on_key_press(self, symbol: int, modifiers: int) -> bool:
        now = time.perf_counter()
        if symbol == self._trigger:
            self._keys.append(KeyPress(TRIGGER, now))
        elif symbol == key.ESCAPE:
            self._keys.append(KeyPress(ABORT, now))
        return pyglet.event.EVENT_HANDLED

    def _on_close(self) -> bool:
        self._keys.append(KeyPress(ABORT, time.perf_counter()))
        return pyglet.event.EVENT_HANDLED

    def describe(self) -> str:
        s = self._screen
        return (
            f"screen={s.width}x{s.height}@({s.x},{s.y}); "
            f"window={self.window.width}x{self.window.height}; "
            f"px_per_cm={self._px_per_cm:.3f}; px_per_deg_at_centre={self._px_per_deg_centre:.3f}; "
            f"outer_radius_px={self._outer_px:.1f}; "
            f"gl_renderer={gl.gl_info.get_renderer()}; pyglet={pyglet.version}"
        )

    def poll_keys(self) -> list[KeyPress]:
        self.window.dispatch_events()
        keys, self._keys = self._keys, []
        return keys

    def draw(self, frame: FrameState) -> None:
        self.window.switch_to()
        self.window.clear()
        if frame.countdown is not None:
            text = str(frame.countdown)
            if self._countdown_label.text != text:  # re-layout only when the number changes
                self._countdown_label.text = text
            self._waiting_batch.draw()
            return
        if frame.show_checkerboard:
            self._textures[int(frame.inverted)].blit(*self._origin)
        self._batch.draw()

    def flip(self) -> float:
        self.window.flip()
        # Block until the GPU has actually finished, so the timestamp is close to the
        # vertical retrace rather than to when the swap was merely queued.
        gl.glFinish()
        return time.perf_counter()

    def close(self) -> None:
        self.window.close()
