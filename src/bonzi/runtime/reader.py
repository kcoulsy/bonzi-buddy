"""Bonzi's Storybook Reader — a Qt port of ``BBReader`` (``Form1``/``Form2``).

The original was a separate ``BBReader.exe`` that opened illustrated "Bonz"
books: each book is a folder of page images (``page0.jpg`` … ``page16.jpg``)
plus a ``book`` XML manifest that declares the image ``fileFormat`` and the
spoken text of every page under ``/book/bookPages/pageN``. Bonzi turns the
"leaves" and reads each page aloud.

Here that becomes an in-process :class:`ReaderDialog`. It lists the books under
``assets/Books``, shows the current page image scaled to fit, and offers
Back / Next / Close plus a "Read to me" toggle that drives the on-screen Bonzi's
:meth:`~bonzi.runtime.pet.BonziPet.say` and auto-advances when he finishes a
page. Page text carries the same MS-Agent speech markup (``\\Pit=…\\``,
``\\emp\\``, ``\\Map="spoken"="written"\\``) used elsewhere, so we reuse
:func:`bonzi.content.clean_lyric` to render a clean, readable line.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING
from xml.etree import ElementTree

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import content
from ..resources import asset

if TYPE_CHECKING:
    from .pet import BonziPet

_PAGE_TAG = re.compile(r"page(\d+)")


def books_root() -> Path:
    """Directory that holds one folder per book."""
    return asset("Books")


class Book:
    """One illustrated book: a folder of page images plus a ``book`` manifest.

    Page indices, the image ``fileFormat`` and each page's spoken text all come
    from the ``book`` XML file. If the manifest is missing or unreadable we fall
    back to enumerating ``pageN.jpg`` files so the pictures still turn.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.name = path.name
        self._fmt = ".jpg"
        self._texts: dict[int, str] = {}
        self._load_manifest()

    def _load_manifest(self) -> None:
        manifest = self.path / "book"
        if manifest.exists():
            try:
                root = ElementTree.fromstring(
                    manifest.read_text(encoding="utf-8", errors="replace")
                )
            except ElementTree.ParseError:
                root = None
            if root is not None:
                fmt = root.findtext("fileFormat")
                if fmt and fmt.strip():
                    self._fmt = fmt.strip()
                pages = root.find("bookPages")
                for el in pages if pages is not None else []:
                    m = _PAGE_TAG.fullmatch(el.tag)
                    if m:
                        self._texts[int(m.group(1))] = el.text or ""
        if not self._texts:
            # No manifest text: derive pages from the image files on disk.
            for img in self.path.glob(f"page*{self._fmt}"):
                m = _PAGE_TAG.fullmatch(img.stem)
                if m:
                    self._texts.setdefault(int(m.group(1)), "")

    @property
    def pages(self) -> list[int]:
        """Sorted page indices that make up the reading flow."""
        return sorted(self._texts)

    def image_path(self, index: int) -> Path:
        """Path to the ``pageN`` image (may not exist for a bad book)."""
        return self.path / f"page{index}{self._fmt}"

    def page_text(self, index: int) -> str:
        """Clean, readable text for a page (empty if it has none)."""
        return content.clean_lyric(self._texts.get(index, ""))


def list_books() -> list[Book]:
    """Every book under :func:`books_root`, alphabetical, with pages only."""
    root = books_root()
    if not root.is_dir():
        return []
    books = [Book(p) for p in sorted(root.iterdir()) if p.is_dir()]
    return [b for b in books if b.pages]


class ReaderDialog(QDialog):
    """Reads one :class:`Book`: a scaled page image plus navigation controls."""

    def __init__(
        self, book: Book, pet: BonziPet | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._book = book
        self._pet = pet
        self._pages = book.pages
        self._index = 0
        self._reading = False
        self._pixmap: QPixmap | None = None

        self.setWindowTitle("BonziBUDDY Storybook Reader")
        self.resize(460, 500)

        self._title = QLabel(book.name)
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = self._title.font()
        title_font.setBold(True)
        self._title.setFont(title_font)

        self._image = QLabel()
        self._image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image.setMinimumSize(1, 1)

        self._page_label = QLabel()
        self._page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._back = QPushButton("◀ Back")
        self._next = QPushButton("Next ▶")
        self._read = QPushButton("Read to me")
        self._read.setCheckable(True)
        close = QPushButton("Close")
        self._back.clicked.connect(lambda: self._go(-1))
        self._next.clicked.connect(lambda: self._go(1))
        self._read.toggled.connect(self._on_toggle_read)
        close.clicked.connect(self.close)

        controls = QHBoxLayout()
        controls.addWidget(self._back)
        controls.addWidget(self._read)
        controls.addWidget(self._next)
        controls.addStretch(1)
        controls.addWidget(close)

        layout = QVBoxLayout(self)
        layout.addWidget(self._title)
        layout.addWidget(self._image, 1)
        layout.addWidget(self._page_label)
        layout.addLayout(controls)

        # Auto-advance uses the pet's speech-finished signal when TTS is really
        # audible; otherwise a length-based timer keeps the pages turning.
        self._advance_timer = QTimer(self)
        self._advance_timer.setSingleShot(True)
        self._advance_timer.timeout.connect(self._advance_after_speech)
        if self._pet is not None:
            self._pet.tts.stopped.connect(self._on_speech_finished)

        self._update_page()

    # -- page display --

    def _update_page(self) -> None:
        index = self._pages[self._index]
        self._pixmap = QPixmap(str(self._book.image_path(index)))
        if self._pixmap.isNull():
            self._pixmap = None
            self._image.setText(f"(missing page {index})")
        else:
            self._rescale()
        self._page_label.setText(f"Page {self._index + 1} of {len(self._pages)}")
        self._back.setEnabled(self._index > 0)
        self._next.setEnabled(self._index < len(self._pages) - 1)

    def _rescale(self) -> None:
        if self._pixmap is None:
            return
        self._image.setPixmap(
            self._pixmap.scaled(
                self._image.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().resizeEvent(event)
        self._rescale()

    # -- navigation --

    def _go(self, delta: int) -> None:
        new = self._index + delta
        if not 0 <= new < len(self._pages):
            return
        self._index = new
        self._update_page()
        if self._reading:
            # Restart speech on the freshly turned page (mirrors the original).
            self._read_current()

    # -- "Read to me" --

    def _on_toggle_read(self, checked: bool) -> None:
        if checked:
            self._reading = True
            self._read_current()
        else:
            self._stop_reading()

    def _read_current(self) -> None:
        """Speak the current page and arm whatever advances us to the next."""
        if not self._reading or self._pet is None:
            return
        self._advance_timer.stop()
        self._pet.tts.stop()  # cancel any speech still in flight
        text = self._book.page_text(self._pages[self._index])
        if text:
            self._pet.say(text)
        # pet.say() only routes through the audible engine (and thus emits
        # ``tts.stopped``) when TTS is both available and unmuted; match that
        # test exactly, else drive the advance from a readable-length timer.
        audible = bool(text) and self._pet.tts.available and self._pet.settings.tts_enabled
        if not audible:
            self._advance_timer.start(1200 + 45 * len(text) if text else 700)

    def _on_speech_finished(self) -> None:
        # The pet's TTS finished; only advance if we started that speech.
        if self._reading:
            self._advance_after_speech()

    def _advance_after_speech(self) -> None:
        if not self._reading:
            return
        if self._index >= len(self._pages) - 1:
            self._stop_reading()  # reached the end of the book
            return
        self._index += 1
        self._update_page()
        self._read_current()

    def _stop_reading(self) -> None:
        self._reading = False
        self._advance_timer.stop()
        if self._pet is not None:
            self._pet.tts.stop()
        if self._read.isChecked():
            self._read.setChecked(False)  # re-enters _on_toggle_read harmlessly

    # -- lifecycle --

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self._stop_reading()
        if self._pet is not None:
            try:
                self._pet.tts.stopped.disconnect(self._on_speech_finished)
            except (RuntimeError, TypeError):
                pass
        super().closeEvent(event)
