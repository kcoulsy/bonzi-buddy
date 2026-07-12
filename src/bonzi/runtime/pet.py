"""The on-screen Bonzi: a frameless, always-on-top, draggable desktop pet."""

from __future__ import annotations

import random

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QCursor, QPainter, QPixmap
from PySide6.QtWidgets import QInputDialog, QMenu, QWidget

from ..acs.model import Character
from .balloon import Balloon
from .player import AnimationPlayer
from .tts import TtsEngine

# animation names present in Bonzi.acs, grouped by intent
IDLE_ANIMS = [
    "Idle1_1", "Idle1_3", "Idle1_5", "Idle1_6", "Idle1_9",
    "Idle1_11", "Idle1_13", "Idle1_14", "Idle1_15", "Idle1_24",
]
TALK_ANIM = "Explain"
GREET_ANIM = "Greet"
SHOW_ANIM = "Show"
HIDE_ANIM = "Hide"
REST_ANIM = "RestPose"


class BonziPet(QWidget):
    quit_requested = Signal()

    def __init__(self, char: Character) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self.char = char
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle(char.name or "Bonzi")
        self.setFixedSize(char.width, char.height)

        self._pix: QPixmap | None = None
        self._drag_offset: QPoint | None = None
        self._speaking = False
        self._busy = False  # a one-shot animation (greet/idle/emote) is playing

        self.player = AnimationPlayer(char, self)
        self.player.frame_ready.connect(self._on_frame)
        self.player.finished.connect(self._on_anim_finished)

        self.tts = TtsEngine(char.voice, self)
        self.tts.stopped.connect(self._on_tts_stopped)

        self.balloon = Balloon()

        self._idle_timer = QTimer(self)
        self._idle_timer.timeout.connect(self._maybe_idle)
        self._idle_timer.start(9000)

        self._place_bottom_right()

    # -- placement / painting --

    def _place_bottom_right(self) -> None:
        screen = self.screen().availableGeometry()
        self.move(screen.right() - self.width() - 40, screen.bottom() - self.height() - 40)

    def _on_frame(self, pix: QPixmap) -> None:
        self._pix = pix
        self.update()
        if self.balloon.isVisible():
            self._reposition_balloon()

    def paintEvent(self, _event) -> None:
        if self._pix is not None:
            QPainter(self).drawPixmap(0, 0, self._pix)

    # -- lifecycle --

    def enter(self) -> None:
        """Show + greet on startup."""
        self.show()
        if not self.player.play(SHOW_ANIM):
            self.player.play(REST_ANIM)
        QTimer.singleShot(600, lambda: self.say("Hello! I'm Bonzi. Right-click me!"))

    def leave(self) -> None:
        self.tts.stop()
        self.balloon.hide()
        self.player.play(HIDE_ANIM)
        QTimer.singleShot(900, self.quit_requested.emit)

    # -- speech --

    def say(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        self._speaking = True
        self._show_balloon(text)
        if self.tts.available:
            self.tts.started.connect(self._noop)
            self.tts.speak(text)
        else:
            # no engine: keep the balloon up a readable while
            QTimer.singleShot(1500 + 40 * len(text), self._on_tts_stopped)
        self._talk_loop()

    def _noop(self) -> None:
        pass

    def _talk_loop(self) -> None:
        if self._speaking:
            if not self.player.play(TALK_ANIM):
                self.player.play(REST_ANIM)

    def _on_tts_stopped(self) -> None:
        self._speaking = False
        self.balloon.hide()
        self.player.play(REST_ANIM)

    def _show_balloon(self, text: str) -> None:
        self._pending_balloon_text = text
        self._reposition_balloon(text)

    def _reposition_balloon(self, text: str | None = None) -> None:
        text = text if text is not None else getattr(self, "_pending_balloon_text", "")
        if not text:
            return
        g = self.geometry()
        self.balloon.show_text(text, g.center().x(), g.top() + 20)

    # -- idle behaviour --

    def _maybe_idle(self) -> None:
        if self._speaking or self._busy or self.player.current_name:
            return
        self._busy = True
        if not self.player.play(random.choice(IDLE_ANIMS)):
            self._busy = False

    def _on_anim_finished(self, name: str) -> None:
        self._busy = False
        if self._speaking and name == TALK_ANIM:
            self._talk_loop()  # keep gesturing until TTS ends
            return
        if not self._speaking and name not in (HIDE_ANIM,):
            self.player.play(REST_ANIM)

    def play_animation(self, name: str) -> None:
        self._busy = True
        self.player.play(name)

    # -- mouse: drag + menu --

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        elif event.button() == Qt.MouseButton.RightButton:
            self._show_menu()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_offset is not None:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            if self.balloon.isVisible():
                self._reposition_balloon()

    def mouseReleaseEvent(self, _event) -> None:
        self._drag_offset = None

    def mouseDoubleClickEvent(self, _event) -> None:
        self.player.play(GREET_ANIM)
        self._busy = True

    def _show_menu(self) -> None:
        menu = QMenu()
        act_say = QAction("Say something…", menu)
        act_say.triggered.connect(self._prompt_say)
        menu.addAction(act_say)

        act_joke = QAction("Tell me a joke", menu)
        act_joke.triggered.connect(self._joke)
        menu.addAction(act_joke)

        anim_menu = menu.addMenu("Animate")
        for name in sorted(a.name for a in self.char.animations):
            act = QAction(name, anim_menu)
            act.triggered.connect(lambda _=False, n=name: self.play_animation(n))
            anim_menu.addAction(act)

        menu.addSeparator()
        act_quit = QAction("Goodbye (quit)", menu)
        act_quit.triggered.connect(self.leave)
        menu.addAction(act_quit)
        menu.exec(QCursor.pos())

    def _prompt_say(self) -> None:
        text, ok = QInputDialog.getText(self, "Bonzi", "What should I say?")
        if ok and text:
            self.say(text)

    def _joke(self) -> None:
        self.play_animation("Pleased")
        self.say(random.choice(_JOKES))


_JOKES = [
    "Why did the computer go to the doctor? It had a virus!",
    "I'm not saying I'm Batman, I'm just saying nobody has ever seen me and Batman in the same room.",
    "Why was the math book sad? It had too many problems.",
    "I told my computer I needed a break, and now it won't stop sending me KitKats.",
    "What do you call a monkey in a minefield? A ba-boom!",
]
