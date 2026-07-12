"""Offscreen smoke test for the Storybook Reader feature.

Enumerates the bundled books, loads a page image, extracts (and cleans) a page's
text, and opens the dialog to walk a couple of pages. Run with::

    QT_QPA_PLATFORM=offscreen PYTHONPATH=src python tests/test_reader.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from PySide6.QtGui import QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from bonzi.runtime.reader import Book, ReaderDialog, books_root, list_books  # noqa: E402

# QPixmap and QDialog need a running application instance.
_app = QApplication.instance() or QApplication([])


def test_enumerate_books() -> None:
    books = list_books()
    assert books, f"no books found under {books_root()}"
    for book in books:
        assert book.name
        assert book.pages, f"{book.name} has no pages"
        # page indices should start at 0 and be contiguous-ish story pages
        assert book.pages[0] == 0


def test_page_image_loads() -> None:
    book = list_books()[0]
    first = book.pages[0]
    path = book.image_path(first)
    assert path.exists(), f"missing page image {path}"
    pix = QPixmap(str(path))
    assert not pix.isNull(), f"could not decode {path}"
    assert pix.width() > 0 and pix.height() > 0


def test_page_text_extracts_clean() -> None:
    for book in list_books():
        got_text = False
        for index in book.pages:
            text = book.page_text(index)
            assert isinstance(text, str)
            # cleaned text must not carry raw MS-Agent speech markup
            assert "\\Pit=" not in text
            assert "\\emp\\" not in text
            assert "\\Map=" not in text
            if text:
                got_text = True
        assert got_text, f"{book.name} yielded no page text at all"


def test_missing_book_is_safe() -> None:
    """A folder with no manifest and no page images has no pages."""
    empty = Book(Path("/nonexistent-book-folder"))
    assert empty.pages == []


def test_dialog_opens_and_navigates() -> None:
    app = _app
    book = list_books()[0]
    dlg = ReaderDialog(book)  # no pet: speech is a no-op, navigation still works
    dlg.show()
    app.processEvents()

    assert dlg._index == 0
    dlg._go(1)
    app.processEvents()
    assert dlg._index == 1
    dlg._go(-1)
    assert dlg._index == 0

    dlg.close()
    app.processEvents()


def _main() -> int:
    test_enumerate_books()
    test_page_image_loads()
    test_page_text_extracts_clean()
    test_missing_book_is_safe()
    test_dialog_opens_and_navigates()
    print("reader smoke test: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
