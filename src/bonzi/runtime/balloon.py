"""A classic Microsoft Agent style speech balloon (frameless, on-top)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

_PAD = 12
_MAX_W = 260
_TAIL = 12


class Balloon(QWidget):
    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._text = ""
        self._lines: list[str] = []
        self._font = QFont("Sans Serif", 10)

    def _wrap(self, text: str) -> list[str]:
        fm = QFontMetrics(self._font)
        lines: list[str] = []
        for para in text.split("\n"):
            words = para.split(" ")
            cur = ""
            for w in words:
                trial = f"{cur} {w}".strip()
                if fm.horizontalAdvance(trial) > _MAX_W and cur:
                    lines.append(cur)
                    cur = w
                else:
                    cur = trial
            lines.append(cur)
        return lines

    def show_text(self, text: str, anchor_center_x: int, anchor_top_y: int) -> None:
        self._text = text
        self._lines = self._wrap(text)
        fm = QFontMetrics(self._font)
        w = min(_MAX_W, max((fm.horizontalAdvance(ln) for ln in self._lines), default=0)) + _PAD * 2
        h = fm.height() * len(self._lines) + _PAD * 2 + _TAIL
        self.resize(w, h)
        # place so the tail points down at the character's head
        self.move(int(anchor_center_x - w / 2), int(anchor_top_y - h))
        self.show()
        self.raise_()
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        body_h = h - _TAIL

        path = QPainterPath()
        path.addRoundedRect(0, 0, w - 1, body_h - 1, 10, 10)
        # downward tail near the horizontal centre
        cx = w / 2
        path.moveTo(cx - 10, body_h - 2)
        path.lineTo(cx, h - 2)
        path.lineTo(cx + 10, body_h - 2)

        p.setPen(QPen(QColor(90, 90, 90), 1))
        p.setBrush(QColor(255, 255, 224))  # pale yellow, like the original
        p.drawPath(path)

        p.setPen(QColor(20, 20, 20))
        p.setFont(self._font)
        fm = QFontMetrics(self._font)
        y = _PAD + fm.ascent()
        for ln in self._lines:
            p.drawText(_PAD, y, ln)
            y += fm.height()
        p.end()
