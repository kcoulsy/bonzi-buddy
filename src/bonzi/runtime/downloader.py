"""Bonzi's Download Manager — a Qt port of ``BonziDownloader.cs``.

A standalone ``QMainWindow`` listing user-added files to fetch. The list is
persisted as XML (schema ``/Files/File`` with ``FileDesc``/``FileStatus``/
``FileSize``/``FileTime``/``FileSite``/``FileInfo``) under the app's
``AppDataLocation``. Downloads run asynchronously through
``QNetworkAccessManager`` and Bonzi announces completion via the pet's
``say()``.

Safety: nothing is ever downloaded or run automatically. A file is only ever
launched (the "Run" action, or the opt-in *launch on complete* option) when it
is one the user themselves added and downloaded — i.e. a local path recorded in
``FileInfo`` after a successful download.
"""

from __future__ import annotations

import random
from datetime import datetime
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol
from urllib.parse import unquote, urlparse
from xml.etree import ElementTree as ET

from PySide6.QtCore import QStandardPaths, QUrl, Qt
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtNetwork import (
    QNetworkAccessManager,
    QNetworkReply,
    QNetworkRequest,
)
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QCheckBox,
    QHeaderView,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from .settings import Settings

# XML element names, in table-column order (Done is runtime-only, not stored).
FIELDS = ("FileDesc", "FileStatus", "FileSize", "FileTime", "FileSite", "FileInfo")

COLUMNS = (
    "File Name/Description",
    "Status",
    "Size (K)",
    "Done (K)",
    "Time",
    "Site",
    "Local File Info",
)

# completion lines Bonzi picks from, mirroring the original's Rnd.Next switch
_DONE_LINES = (
    "{name}, I'm done downloading the file - {file}.",
    "I've successfully downloaded the file - {file}.",
    "I've finished downloading the file - {file}.",
)


class PetLike(Protocol):
    """The slice of :class:`~bonzi.runtime.pet.BonziPet` the manager uses."""

    settings: Settings

    def say(self, text: str) -> None: ...
    def play_animation(self, name: str) -> None: ...


@dataclass
class DownloadEntry:
    """One row of the download list; ``site`` is the URL, ``info`` the local path."""

    desc: str = ""
    status: str = "NEW"
    size: str = ""
    time: str = ""
    site: str = ""
    info: str = "None"

    def as_fields(self) -> tuple[str, str, str, str, str, str]:
        return (self.desc, self.status, self.size, self.time, self.site, self.info)


@dataclass
class DownloadStore:
    """Loads/saves the download list as XML at ``path``."""

    path: Path
    entries: list[DownloadEntry] = field(default_factory=list)

    def load(self) -> None:
        self.entries = []
        if not self.path.exists():
            return
        try:
            root = ET.parse(self.path).getroot()
        except ET.ParseError:
            return
        for node in root.findall("File"):
            self.entries.append(
                DownloadEntry(
                    desc=_text(node, "FileDesc"),
                    status=_text(node, "FileStatus") or "NEW",
                    size=_text(node, "FileSize"),
                    time=_text(node, "FileTime"),
                    site=_text(node, "FileSite"),
                    info=_text(node, "FileInfo") or "None",
                )
            )

    def save(self) -> None:
        root = ET.Element("Files")
        for entry in self.entries:
            file_el = ET.SubElement(root, "File")
            for tag, value in zip(FIELDS, entry.as_fields()):
                ET.SubElement(file_el, tag).text = value
        self.path.parent.mkdir(parents=True, exist_ok=True)
        ET.indent(root)
        ET.ElementTree(root).write(self.path, encoding="utf-8", xml_declaration=True)

    def find_by_site(self, site: str) -> DownloadEntry | None:
        return next((e for e in self.entries if e.site == site), None)


def _text(node: ET.Element, tag: str) -> str:
    child = node.find(tag)
    return (child.text or "") if child is not None else ""


def _default_xml_path() -> Path:
    root = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppDataLocation
    )
    return Path(root or Path.home() / ".bonzi") / "downloads.xml"


def _downloads_dir() -> Path:
    loc = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.DownloadLocation
    )
    return Path(loc) if loc else Path.home() / "Downloads"


def _filename_from_url(url: str) -> str:
    name = Path(unquote(urlparse(url).path)).name
    return name or "download"


def _is_valid_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


class LinkDialog(QDialog):
    """Add/Edit dialog collecting a description and a URL."""

    def __init__(self, parent: QWidget | None, title: str, desc: str, url: str) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self._desc = QLineEdit(desc)
        self._url = QLineEdit(url)
        self._url.setPlaceholderText("https://example.com/file.zip")

        form = QFormLayout(self)
        form.addRow("File Description:", self._desc)
        form.addRow("File URL (Internet Address):", self._url)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self.resize(420, self.sizeHint().height())

    @property
    def description(self) -> str:
        return self._desc.text().strip()

    @property
    def url(self) -> str:
        return self._url.text().strip()


class DownloadOptionsDialog(QDialog):
    """The two download options (DMOptions.cs), both defaulting off."""

    def __init__(self, settings: Settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Bonzi's Download Manager - Options")
        self._s = settings
        self._prompt = QCheckBox("Prompt for a folder before each download")
        self._prompt.setChecked(settings.dm_prompt_folder)
        self._run = QCheckBox("Launch or install the file after download completes")
        self._run.setChecked(settings.dm_run_on_complete)

        form = QFormLayout(self)
        form.addRow(self._prompt)
        form.addRow(self._run)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _save(self) -> None:
        self._s.dm_prompt_folder = self._prompt.isChecked()
        self._s.dm_run_on_complete = self._run.isChecked()
        self.accept()


class DownloadManager(QMainWindow):
    """The Download Manager window. Keep a single instance per pet."""

    def __init__(self, pet: PetLike | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Bonzi's Download Manager")
        self.resize(720, 360)

        self._pet = pet
        self._settings = pet.settings if pet is not None else Settings()
        self._store = DownloadStore(_default_xml_path())
        self._nam = QNetworkAccessManager(self)
        # reply -> (entry, destination path) for the in-flight download
        self._active: dict[QNetworkReply, tuple[DownloadEntry, Path]] = {}

        self._build_ui()
        self._store.load()
        self.refresh()
        self._update_actions()

    # -- UI construction --

    def _build_ui(self) -> None:
        toolbar = QToolBar("Actions", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        def act(label: str, slot) -> QAction:
            action = QAction(label, self)
            action.triggered.connect(slot)
            toolbar.addAction(action)
            return action

        self._a_download = act("Download", self._on_download)
        self._a_stop = act("Stop", self._on_stop)
        toolbar.addSeparator()
        self._a_run = act("Run", self._on_run)
        toolbar.addSeparator()
        self._a_add = act("Add", self._on_add)
        self._a_edit = act("Edit", self._on_edit)
        self._a_remove = act("Remove", self._on_remove)
        self._a_delete = act("Delete", self._on_delete)
        toolbar.addSeparator()
        self._a_options = act("Options", self._on_options)
        toolbar.addSeparator()
        act("Exit", self.close)

        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(6, 6, 6, 6)

        self._table = QTableWidget(0, len(COLUMNS), central)
        self._table.setHorizontalHeaderLabels(COLUMNS)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._table.itemSelectionChanged.connect(self._update_actions)
        layout.addWidget(self._table)

        self._progress = QProgressBar(central)
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        layout.addWidget(self._progress)

        self.setCentralWidget(central)
        self.statusBar().showMessage("Idle")

    # -- list rendering --

    def refresh(self) -> None:
        """Rebuild the table from the store (Status 'NEW' shows blank)."""
        self._table.setRowCount(len(self._store.entries))
        for row, entry in enumerate(self._store.entries):
            status = "" if entry.status == "NEW" else entry.status
            cells = (entry.desc, status, entry.size, "", entry.time, entry.site, entry.info)
            for col, value in enumerate(cells):
                self._table.setItem(row, col, QTableWidgetItem(value))
        self._update_actions()

    def _selected_row(self) -> int:
        rows = self._table.selectionModel().selectedRows()
        return rows[0].row() if rows else -1

    def _selected_entry(self) -> DownloadEntry | None:
        row = self._selected_row()
        return self._store.entries[row] if 0 <= row < len(self._store.entries) else None

    def _set_cell(self, row: int, col: int, text: str) -> None:
        item = self._table.item(row, col)
        if item is None:
            item = QTableWidgetItem()
            self._table.setItem(row, col, item)
        item.setText(text)

    def _update_actions(self) -> None:
        entry = self._selected_entry()
        has = entry is not None
        downloading = bool(self._active)
        self._a_download.setEnabled(has and not downloading)
        self._a_run.setEnabled(has)
        self._a_edit.setEnabled(has)
        self._a_remove.setEnabled(has)
        self._a_stop.setEnabled(downloading)
        # Delete only makes sense once there's a real local file recorded.
        self._a_delete.setEnabled(has and entry.info not in ("", "None"))

    # -- Bonzi helpers --

    def _say(self, text: str) -> None:
        if self._pet is not None:
            self._pet.say(text)

    def _play(self, anim: str) -> None:
        if self._pet is not None:
            self._pet.play_animation(anim)

    def _name(self) -> str:
        return self._settings.name

    # -- toolbar actions --

    def _on_add(self) -> None:
        dialog = LinkDialog(self, "Add File to Download List", "", "")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        url = dialog.url
        if not url:
            self._say("Please enter a URL first!")
            return
        if not _is_valid_url(url):
            self._say("Please enter a valid URL.")
            return
        if self._store.find_by_site(url) is not None:
            self._say("Sorry, that file URL is already in use.")
            return
        desc = dialog.description or _filename_from_url(url)
        self._store.entries.append(
            DownloadEntry(
                desc=desc,
                status="NEW",
                size="",
                time=datetime.now().strftime("%I:%M %p").lstrip("0"),
                site=url,
                info="None",
            )
        )
        self._store.save()
        self.refresh()

    def _on_edit(self) -> None:
        entry = self._selected_entry()
        if entry is None:
            return
        dialog = LinkDialog(self, "Edit Entry", entry.desc, entry.site)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        url = dialog.url
        if not _is_valid_url(url):
            self._say("Please enter a valid URL.")
            return
        entry.desc = dialog.description or _filename_from_url(url)
        entry.site = url
        entry.status = "NEW"
        entry.size = ""
        entry.info = "None"
        self._store.save()
        self.refresh()

    def _on_remove(self) -> None:
        entry = self._selected_entry()
        if entry is None:
            return
        confirm = QMessageBox.question(
            self,
            "BonziBUDDY",
            "Are you sure you wish to remove the selected file from the download list?",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self._store.entries.remove(entry)
        self._store.save()
        self.refresh()

    def _on_delete(self) -> None:
        """Delete the downloaded local file from disk (keeps the list entry)."""
        entry = self._selected_entry()
        if entry is None or entry.info in ("", "None"):
            return
        confirm = QMessageBox.question(
            self,
            "BonziBUDDY",
            "Are you sure you wish to delete the downloaded file from your computer?",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            Path(entry.info).unlink(missing_ok=True)
        except OSError as exc:  # pragma: no cover - depends on filesystem state
            QMessageBox.warning(self, "BonziBUDDY", str(exc))
            return
        entry.info = "None"
        self._store.save()
        self.refresh()

    def _on_options(self) -> None:
        DownloadOptionsDialog(self._settings, self).exec()

    def _on_run(self) -> None:
        entry = self._selected_entry()
        if entry is None:
            return
        # Only ever open a file the user downloaded themselves.
        if entry.info in ("", "None") or not Path(entry.info).exists():
            self._play("Surprised")
            self._say(
                f"There was an error running the file - {entry.desc}. "
                "Please download the file first before running!"
            )
            return
        self._launch(entry.info)

    def _launch(self, path: str) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _on_stop(self) -> None:
        if not self._active:
            return
        for reply, (entry, _dest) in list(self._active.items()):
            row = self._store.entries.index(entry)
            self._set_cell(row, 1, "Canceled")
            reply.abort()
        self._progress.setValue(0)
        self.statusBar().showMessage("Idle")

    def _on_download(self) -> None:
        entry = self._selected_entry()
        if entry is None or self._active:
            return
        url = entry.site
        if not _is_valid_url(url):
            self._say("That doesn't look like a valid URL.")
            return

        dest_dir = _downloads_dir()
        if self._settings.dm_prompt_folder:
            chosen = QFileDialog.getExistingDirectory(
                self, "Choose a download folder", str(dest_dir)
            )
            if not chosen:
                return
            dest_dir = Path(chosen)
        dest = dest_dir / _filename_from_url(url)

        row = self._store.entries.index(entry)
        reply = self._nam.get(QNetworkRequest(QUrl(url)))
        self._active[reply] = (entry, dest)
        reply.downloadProgress.connect(
            lambda got, total, r=reply: self._on_progress(r, got, total)
        )
        reply.finished.connect(lambda r=reply: self._on_finished(r))

        self._set_cell(row, 1, "Locating...")
        self.statusBar().showMessage(f"Locating file - {dest.name}")
        self._update_actions()

        self._play("Wave")
        self._say(
            f"{self._name()}, I'll handle downloading. Sit back and relax my friend! "
            f"I'll now go get the file - {dest.name} for you."
        )

    # -- network callbacks --

    def _on_progress(self, reply: QNetworkReply, received: int, total: int) -> None:
        pair = self._active.get(reply)
        if pair is None:
            return
        entry, _dest = pair
        row = self._store.entries.index(entry)
        self._set_cell(row, 1, "Downloading...")
        if total > 0:
            self._set_cell(row, 2, f"{total / 1024:.0f}")
            self._progress.setValue(int(received / total * 100))
        self._set_cell(row, 3, f"{received / 1024:.0f}")
        self.statusBar().showMessage(
            f"Downloading file - {_filename_from_url(entry.site)}"
        )

    def _on_finished(self, reply: QNetworkReply) -> None:
        pair = self._active.pop(reply, None)
        reply.deleteLater()
        self._progress.setValue(0)
        self.statusBar().showMessage("Idle")
        self._update_actions()
        if pair is None:
            return
        entry, dest = pair

        if reply.error() != QNetworkReply.NetworkError.NoError:
            # aborted (Stop) or a real failure — leave the status as-is/failed.
            if reply.error() != QNetworkReply.NetworkError.OperationCanceledError:
                row = self._store.entries.index(entry)
                self._set_cell(row, 1, "Failed")
            return

        data = bytes(reply.readAll().data())
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
        except OSError as exc:  # pragma: no cover - depends on filesystem state
            QMessageBox.warning(self, "BonziBUDDY", str(exc))
            return

        entry.status = "Download Complete"
        entry.size = f"{len(data) / 1024:.0f}"
        entry.info = str(dest)
        self._store.save()

        row = self._store.entries.index(entry)
        self._set_cell(row, 1, entry.status)
        self._set_cell(row, 2, entry.size)
        self._set_cell(row, 6, entry.info)
        self._update_actions()

        self._play("GetAttention")
        self._say(random.choice(_DONE_LINES).format(name=self._name(), file=dest.name))

        # Opt-in only, and only for this file the user added + downloaded.
        if self._settings.dm_run_on_complete:
            self._launch(entry.info)

    # -- window lifecycle --

    def closeEvent(self, event) -> None:
        if self._active:
            # a download is running: hide instead of tearing it down
            event.ignore()
            self.hide()
        else:
            event.accept()
