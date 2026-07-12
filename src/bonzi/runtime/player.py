"""Frame-stepping animation player for a parsed Microsoft Agent character.

Plays an animation frame by frame honouring each frame's duration and the
format's probabilistic branch table (used for idle loops and gestures). Emits a
composited ``QPixmap`` per frame and a signal when the animation ends.
"""

from __future__ import annotations

import random

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QImage, QPainter, QPixmap

from ..acs.model import Animation, Character, Frame


def _sprite_to_qimage(rgba: bytes, w: int, h: int) -> QImage:
    # Image.rgba is top-down straight-alpha bytes in R,G,B,A order == RGBA8888.
    return QImage(rgba, w, h, QImage.Format.Format_RGBA8888)


class AnimationPlayer(QObject):
    """Drives one animation at a time and paints composited frames."""

    frame_ready = Signal(QPixmap)
    finished = Signal(str)  # name of the animation that just ended

    def __init__(self, char: Character, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.char = char
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._tick)
        self._anim: Animation | None = None
        self._frame_idx = 0
        self._stop_requested = False
        self._frame_cache: dict[tuple[str, int], QPixmap] = {}

    # -- public API --

    def play(self, name: str) -> bool:
        anim = self.char.animation(name)
        if anim is None or not anim.frames:
            return False
        self._timer.stop()
        self._anim = anim
        self._frame_idx = 0
        self._stop_requested = False
        self._tick()
        return True

    def stop(self) -> None:
        """Ask the current animation to take its exit branch and end."""
        self._stop_requested = True

    def hard_stop(self) -> None:
        self._timer.stop()
        self._anim = None

    @property
    def current_name(self) -> str | None:
        return self._anim.name if self._anim else None

    # -- internals --

    def _composite(self, anim: Animation, idx: int) -> QPixmap:
        key = (anim.name, idx)
        cached = self._frame_cache.get(key)
        if cached is not None:
            return cached
        canvas = QImage(self.char.width, self.char.height, QImage.Format.Format_RGBA8888)
        canvas.fill(0)
        painter = QPainter(canvas)
        frame = anim.frames[idx]
        for fi in frame.images:
            if 0 <= fi.image_index < len(self.char.images):
                sprite = self.char.images[fi.image_index]
                if sprite.width and sprite.height:
                    painter.drawImage(
                        fi.x, fi.y, _sprite_to_qimage(sprite.rgba, sprite.width, sprite.height)
                    )
        painter.end()
        pix = QPixmap.fromImage(canvas)
        self._frame_cache[key] = pix
        return pix

    def _next_index(self, frame: Frame, idx: int) -> int | None:
        """Resolve the next frame index, honouring branches and exit requests."""
        if self._stop_requested and frame.exit_frame is not None:
            return frame.exit_frame
        if frame.branches:
            roll = random.randint(0, 99)
            cum = 0
            for br in frame.branches:
                cum += br.probability
                if roll < cum:
                    return br.frame_index
        nxt = idx + 1
        return nxt if nxt < len(self._anim.frames) else None

    def _tick(self) -> None:
        anim = self._anim
        if anim is None:
            return
        idx = self._frame_idx
        if idx >= len(anim.frames):
            self._finish(anim)
            return

        self.frame_ready.emit(self._composite(anim, idx))
        frame = anim.frames[idx]

        nxt = self._next_index(frame, idx)
        if nxt is None:
            # hold the last frame for its duration, then finish
            QTimer.singleShot(max(1, frame.duration_ms), lambda: self._finish(anim))
            return
        self._frame_idx = nxt
        self._timer.start(max(1, frame.duration_ms))

    def _finish(self, anim: Animation) -> None:
        if self._anim is not anim:
            return
        self._anim = None
        self.finished.emit(anim.name)
