"""The on-screen Bonzi: a frameless, always-on-top, draggable desktop pet."""

from __future__ import annotations

import random

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QCursor, QPainter, QPixmap
from PySide6.QtWidgets import QInputDialog, QMenu, QWidget

from .. import content
from ..acs.model import Character
from . import features
from .balloon import Balloon
from .calendar import (
    ATTENTION_ANIMS,
    AppointmentStore,
    CalendarDialog,
    default_store_path,
    fire_due_reminders,
)
from .downloader import DownloadManager
from .options_dialog import OptionsDialog
from .player import AnimationPlayer
from .reader import Book, ReaderDialog, list_books
from .settings import Settings
from .sound import SoundBank
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
        self.settings = Settings()
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle(char.name or "Bonzi")
        self.setFixedSize(char.width, char.height)

        self._pix: QPixmap | None = None
        self._drag_offset: QPoint | None = None
        self._downloader: DownloadManager | None = None
        self._calendar: CalendarDialog | None = None
        self._reader: ReaderDialog | None = None
        self._speaking = False
        self._busy = False  # a one-shot animation (greet/idle/emote) is playing

        # calendar reminders: a shared JSON store polled by a timer
        self._appointments = AppointmentStore(default_store_path())
        self._attention_anim = next(
            (n for n in ATTENTION_ANIMS if self.char.animation(n)), None
        )

        self.player = AnimationPlayer(char, self)
        self.player.frame_ready.connect(self._on_frame)
        self.player.finished.connect(self._on_anim_finished)

        self.sounds = SoundBank(char.sounds, self)
        self.player.sound_triggered.connect(self.sounds.play)

        self.tts = TtsEngine(char.voice, self)
        self.tts.stopped.connect(self._on_tts_stopped)

        self.balloon = Balloon()

        # lip-sync: swaps mouth shapes while speaking
        self._mouth_timer = QTimer(self)
        self._mouth_timer.timeout.connect(self._animate_mouth)

        self._idle_timer = QTimer(self)
        self._idle_timer.timeout.connect(self._maybe_idle)
        self._idle_timer.start(9000)

        self._reminder_timer = QTimer(self)
        self._reminder_timer.timeout.connect(self._check_reminders)
        self._reminder_timer.start(30_000)

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
        greeting = (
            "Hello! I'm Bonzi. Right-click me to see what I can do!"
            if self.settings.first_run
            else f"Welcome back, {self.settings.name}! Right-click me anytime."
        )
        self.settings.first_run = False
        QTimer.singleShot(700, lambda: self.say(greeting))

    def leave(self) -> None:
        self.tts.stop()
        self.balloon.hide()
        self.player.play(HIDE_ANIM)
        QTimer.singleShot(900, self.quit_requested.emit)

    def cleanup(self) -> None:
        """Stop all timers/audio before the app tears down.

        A repeating timer (mouth lip-sync, idle, reminders) firing into
        half-destroyed Qt objects during shutdown crashes the interpreter, so
        everything must be quiesced here. Wired to QApplication.aboutToQuit.
        """
        self._speaking = False
        for timer in (self._mouth_timer, self._idle_timer, self._reminder_timer):
            timer.stop()
        self.player.hard_stop()
        self.tts.stop()
        self.sounds.stop_all()
        self.balloon.hide()

    # -- speech --

    def say(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        self._speaking = True
        self._show_balloon(text)
        self.player.hard_stop()  # hold the rest pose; the mouth does the work
        if self.tts.available and self.settings.tts_enabled:
            self.tts.speak(text)
        else:
            # no engine (or muted): keep the balloon up a readable while
            QTimer.singleShot(1400 + 45 * len(text), self._on_tts_stopped)

        if self.player.has_mouth_shapes:
            self._mouth_timer.start(85)
            self._animate_mouth()
        else:
            self.player.play(TALK_ANIM) or self.player.play(REST_ANIM)

    def _animate_mouth(self) -> None:
        """Swap mouth shapes to fake visemes while TTS plays."""
        if not self._speaking:
            return
        # bias toward open shapes so it reads as talking; occasional closed pause
        mouth = random.choices([0, 1, 2, 3, 4, 5, 6], weights=[3, 4, 6, 6, 6, 4, 3])[0]
        pix = self.player.speaking_pixmap(mouth)
        if pix is not None:
            self._on_frame(pix)

    def _on_tts_stopped(self) -> None:
        self._speaking = False
        self._mouth_timer.stop()
        self.balloon.hide()
        # settle on the closed mouth, then resume idling
        closed = self.player.speaking_pixmap(0)
        if closed is not None:
            self._on_frame(closed)
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
        if self._speaking:
            return  # lip-sync owns the display while speaking
        if name not in (HIDE_ANIM,):
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

        def add(label: str, slot) -> None:
            act = QAction(label, menu)
            act.triggered.connect(slot)
            menu.addAction(act)

        add("Say something…", self._prompt_say)
        add("Tell me a joke", self._joke)
        add("Tell an amazing fact", self._fact)
        add("Sing me a song", self._sing)

        story_menu = menu.addMenu("Read me a story")
        books = list_books()
        if books:
            for book in books:
                a = QAction(book.name, story_menu)
                a.triggered.connect(lambda _=False, b=book: self._open_reader(b))
                story_menu.addAction(a)
        else:
            none_act = QAction("(no books found)", story_menu)
            none_act.setEnabled(False)
            story_menu.addAction(none_act)
        menu.addSeparator()
        add("Search the web…", self._prompt_search)

        add("Download Manager…", self._open_downloader)
        add("Calendar…", self._open_calendar)
        menu.addSeparator()

        surf = menu.addMenu("Go online")
        for label, url in features.LINKS.items():
            a = QAction(label, surf)
            a.triggered.connect(lambda _=False, u=url: features.open_url(u))
            surf.addAction(a)

        anim_menu = menu.addMenu("Animate")
        for name in sorted(a.name for a in self.char.animations):
            act = QAction(name, anim_menu)
            act.triggered.connect(lambda _=False, n=name: self.play_animation(n))
            anim_menu.addAction(act)

        menu.addSeparator()
        add("Options…", self._options)
        add("Goodbye (quit)", self.leave)
        menu.exec(QCursor.pos())

    def _prompt_say(self) -> None:
        text, ok = QInputDialog.getText(self, "Bonzi", "What should I say?")
        if ok and text:
            self.say(text)

    def _joke(self) -> None:
        self.play_animation("Pleased")
        QTimer.singleShot(400, lambda: self.say(content.random_joke()))

    def _fact(self) -> None:
        self.play_animation("Reading")
        QTimer.singleShot(400, lambda: self.say(content.random_fact()))

    def _sing(self) -> None:
        song = content.random_song()
        if song is None:
            self.say("La la la! I don't have my songbook right now.")
            return
        lyrics = content.song_lyrics(song)
        intro = f"Here's a song for you — {song['title']}, by {song['author']}. ♪"
        self.say(f"{intro} {lyrics}")

    def _prompt_search(self) -> None:
        query, ok = QInputDialog.getText(self, "Bonzi Search", "What shall I search for?")
        if ok and query.strip():
            self.say(f"Let me search the web for {query}!")
            features.search(query.strip(), self.settings.search_engine)

    def _open_reader(self, book: Book) -> None:
        """Open the Storybook Reader for ``book``, one window at a time."""
        if self._reader is not None:
            self._reader.close()
        self._reader = ReaderDialog(book, self)
        self._reader.show()
        self._reader.raise_()
        self._reader.activateWindow()

    def _open_downloader(self) -> None:
        """Open the Download Manager, keeping a single shared instance."""
        if self._downloader is None:
            self._downloader = DownloadManager(self)
        self._downloader.show()
        self._downloader.raise_()
        self._downloader.activateWindow()

    def _open_calendar(self) -> None:
        """Open the Calendar dialog, keeping a single shared instance.

        The dialog owns a separate store over the same JSON file as the reminder
        timer; both read/write the one path, so edits and reminders stay in sync.
        """
        if self._calendar is None:
            self._calendar = CalendarDialog(parent=self)
        else:
            self._calendar.reload()
        self._calendar.show()
        self._calendar.raise_()
        self._calendar.activateWindow()

    def _check_reminders(self) -> None:
        """Poll the appointment store and announce anything now due."""
        self._appointments.load()  # pick up edits made in the dialog / on disk
        fire_due_reminders(
            self._appointments,
            self.say,
            self.play_animation,
            self._attention_anim,
        )

    def _options(self) -> None:
        dlg = OptionsDialog(self.settings, self.tts.available)
        dlg.exec()
