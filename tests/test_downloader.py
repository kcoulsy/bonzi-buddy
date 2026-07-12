"""Offscreen smoke test for the Download Manager.

Adds an entry, round-trips the XML store, and opens the window without error.
Run with::

    QT_QPA_PLATFORM=offscreen PYTHONPATH=src python tests/test_downloader.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from PySide6.QtWidgets import QApplication  # noqa: E402

from bonzi.runtime.downloader import (  # noqa: E402
    FIELDS,
    DownloadEntry,
    DownloadManager,
    DownloadStore,
)


def test_store_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "downloads.xml"
    store = DownloadStore(path)
    store.entries.append(
        DownloadEntry(
            desc="Example file",
            status="NEW",
            size="",
            time="12:00 PM",
            site="https://example.com/file.zip",
            info="None",
        )
    )
    store.save()
    assert path.exists()

    xml = path.read_text(encoding="utf-8")
    for field_name in FIELDS:
        assert f"<{field_name}>" in xml or f"<{field_name} />" in xml

    reloaded = DownloadStore(path)
    reloaded.load()
    assert len(reloaded.entries) == 1
    entry = reloaded.entries[0]
    assert entry.desc == "Example file"
    assert entry.site == "https://example.com/file.zip"
    assert entry.status == "NEW"


def test_window_opens(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])

    window = DownloadManager()
    window._store = DownloadStore(tmp_path / "downloads.xml")
    window._store.entries.append(
        DownloadEntry(desc="Smoke", site="https://example.com/a.bin")
    )
    window._store.save()
    window.refresh()

    assert window._table.rowCount() == 1
    assert window._table.item(0, 0).text() == "Smoke"
    # Status column blank while the entry is still NEW.
    assert window._table.item(0, 1).text() == ""

    window.show()
    app.processEvents()
    window.close()


def _main() -> int:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        test_store_roundtrip(base / "a")
        test_window_opens(base / "b")
    print("downloader smoke test: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
