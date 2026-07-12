"""Bonzi's Calendar & Reminders — a Qt port of ``BonziCalendar.cs`` /
``AppointmentWindow.cs``.

A ``QDialog`` wrapping a :class:`QCalendarWidget`: days that carry appointments
are highlighted, and the panel beside the calendar lists the selected day's
appointments with Add / Edit / Delete actions. Each appointment is a
``(date, time, title, note)`` tuple persisted as JSON under the app's
``AppDataLocation`` (schema: a top-level list of objects).

The original stored events as XML and split the reminder into a separate
date/time; here the appointment's own moment *is* the reminder. A ``QTimer`` in
:class:`~bonzi.runtime.pet.BonziPet` polls :func:`fire_due_reminders` so Bonzi
pops up and speaks when one falls due.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, time
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QDate, QStandardPaths, QTime, Qt
from PySide6.QtGui import QColor, QTextCharFormat
from PySide6.QtWidgets import (
    QCalendarWidget,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

# animations Bonzi tries, in order, to grab attention when a reminder fires
ATTENTION_ANIMS = ("GetAttention", "Alert", "Pleased", "Explain")


@dataclass
class Appointment:
    """A single scheduled item: ``title`` (+ optional ``note``) at a date/time.

    ``reminded`` records that Bonzi has already announced this one, so it is not
    repeated on every timer tick.
    """

    date: date
    time: time
    title: str
    note: str = ""
    reminded: bool = False

    def when(self) -> datetime:
        """The moment this appointment falls due."""
        return datetime.combine(self.date, self.time)

    def to_dict(self) -> dict[str, object]:
        return {
            "date": self.date.isoformat(),
            "time": self.time.strftime("%H:%M"),
            "title": self.title,
            "note": self.note,
            "reminded": self.reminded,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Appointment:
        return cls(
            date=date.fromisoformat(str(data["date"])),
            time=_parse_time(str(data["time"])),
            title=str(data.get("title", "")),
            note=str(data.get("note", "")),
            reminded=bool(data.get("reminded", False)),
        )


def _parse_time(text: str) -> time:
    """Parse ``HH:MM`` (24-hour), tolerating a stray seconds field."""
    parts = text.split(":")
    hour = int(parts[0]) if parts and parts[0] else 0
    minute = int(parts[1]) if len(parts) > 1 and parts[1] else 0
    return time(hour % 24, minute % 60)


@dataclass
class AppointmentStore:
    """Loads/saves the appointment list as JSON at ``path``."""

    path: Path
    appointments: list[Appointment] = field(default_factory=list)

    def load(self) -> None:
        self.appointments = []
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        if not isinstance(raw, list):
            return
        for item in raw:
            if isinstance(item, dict):
                try:
                    self.appointments.append(Appointment.from_dict(item))
                except (KeyError, ValueError):
                    continue

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = [a.to_dict() for a in self.appointments]
        self.path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def on_date(self, day: date) -> list[Appointment]:
        """Appointments on ``day``, ordered by time."""
        return sorted(
            (a for a in self.appointments if a.date == day), key=lambda a: a.time
        )

    def dates_with_appointments(self) -> set[date]:
        return {a.date for a in self.appointments}


def default_store_path() -> Path:
    """The JSON store location under ``AppDataLocation`` (mirrors the DM)."""
    root = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppDataLocation
    )
    return Path(root or Path.home() / ".bonzi") / "appointments.json"


def pop_due_appointments(
    store: AppointmentStore, now: datetime | None = None
) -> list[Appointment]:
    """Return due, not-yet-reminded appointments, marking them + saving."""
    now = now or datetime.now()
    due = [a for a in store.appointments if not a.reminded and a.when() <= now]
    for appt in due:
        appt.reminded = True
    if due:
        store.save()
    return due


def fire_due_reminders(
    store: AppointmentStore,
    say: Callable[[str], None],
    animate: Callable[[str], None] | None = None,
    attention: str | None = None,
    now: datetime | None = None,
) -> list[Appointment]:
    """Announce every due reminder through ``say`` (and optionally ``animate``).

    Returns the appointments that fired. Kept free of any pet dependency so it is
    trivially testable with a stubbed ``say``.
    """
    due = pop_due_appointments(store, now)
    for appt in due:
        if animate is not None and attention:
            animate(attention)
        say(f"Reminder: {appt.title}")
    return due


class AppointmentDialog(QDialog):
    """Add / edit a single appointment's time, title and note."""

    def __init__(
        self, day: date, appt: Appointment | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._day = day
        self.setWindowTitle(
            "Edit appointment" if appt else "Add appointment or task"
        )

        self._title = QLineEdit(appt.title if appt else "")
        self._time = QTimeEdit(
            QTime(appt.time.hour, appt.time.minute) if appt else QTime(12, 0)
        )
        self._time.setDisplayFormat("hh:mm AP")
        self._note = QPlainTextEdit(appt.note if appt else "")
        self._note.setFixedHeight(72)

        form = QFormLayout(self)
        form.addRow(QLabel(f"Appointment or task for {day.strftime('%x')}"))
        form.addRow("Title:", self._title)
        form.addRow("Time:", self._time)
        form.addRow("Note:", self._note)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _accept(self) -> None:
        if not self._title.text().strip():
            QMessageBox.information(
                self,
                "Bonzi",
                "You must enter some text for the appointment before you can save it.",
            )
            return
        self.accept()

    def result_appointment(self) -> Appointment:
        qt = self._time.time()
        return Appointment(
            date=self._day,
            time=time(qt.hour(), qt.minute()),
            title=self._title.text().strip(),
            note=self._note.toPlainText().strip(),
        )


class CalendarDialog(QDialog):
    """The main calendar window: a month view plus the selected day's schedule."""

    def __init__(
        self, store: AppointmentStore | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Bonzi's Calendar")
        self.resize(620, 380)

        self.store = store or AppointmentStore(default_store_path())
        self.store.load()

        self._calendar = QCalendarWidget()
        self._calendar.setGridVisible(True)
        self._calendar.selectionChanged.connect(self._on_date_changed)

        self._day_label = QLabel()
        self._list = QListWidget()
        self._list.itemDoubleClicked.connect(lambda _: self._edit())

        add_btn = QPushButton("&Add")
        edit_btn = QPushButton("&Edit")
        del_btn = QPushButton("&Delete")
        close_btn = QPushButton("&Close")
        add_btn.clicked.connect(self._add)
        edit_btn.clicked.connect(self._edit)
        del_btn.clicked.connect(self._delete)
        close_btn.clicked.connect(self.accept)

        intro = QLabel(
            "I can help keep you on schedule. Enter your appointments, birthdays "
            "and special events, and I'll remind you when they're near."
        )
        intro.setWordWrap(True)

        right = QVBoxLayout()
        right.addWidget(self._day_label)
        right.addWidget(self._list, 1)
        btn_row = QHBoxLayout()
        for btn in (add_btn, edit_btn, del_btn):
            btn_row.addWidget(btn)
        right.addLayout(btn_row)

        body = QHBoxLayout()
        body.addWidget(self._calendar, 1)
        right_panel = QWidget()
        right_panel.setLayout(right)
        body.addWidget(right_panel, 1)

        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addLayout(body, 1)
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        bottom.addWidget(close_btn)
        layout.addLayout(bottom)

        self._highlight_days()
        self._on_date_changed()

    # -- helpers --

    def _selected_date(self) -> date:
        return self._calendar.selectedDate().toPython()

    def _highlight_days(self) -> None:
        """Bold + tint every day that carries at least one appointment."""
        plain = QTextCharFormat()
        self._calendar.setDateTextFormat(QDate(), plain)  # clear all

        marked = QTextCharFormat()
        marked.setFontWeight(75)  # QFont.Bold
        marked.setBackground(QColor(255, 247, 176))
        marked.setToolTip("Has appointments")
        for day in self.store.dates_with_appointments():
            self._calendar.setDateTextFormat(
                QDate(day.year, day.month, day.day), marked
            )

    def _refresh(self) -> None:
        self.store.save()
        self._highlight_days()
        self._on_date_changed()

    def reload(self) -> None:
        """Re-read the store from disk (e.g. after reminders fired elsewhere)."""
        self.store.load()
        self._highlight_days()
        self._on_date_changed()

    # -- slots --

    def _on_date_changed(self) -> None:
        day = self._selected_date()
        self._day_label.setText(f"Schedule for {day.strftime('%x')}")
        self._list.clear()
        for appt in self.store.on_date(day):
            label = f"{appt.time.strftime('%I:%M %p').lstrip('0')}  —  {appt.title}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, appt)
            if appt.note:
                item.setToolTip(appt.note)
            self._list.addItem(item)

    def _selected_appointment(self) -> Appointment | None:
        item = self._list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _add(self) -> None:
        dlg = AppointmentDialog(self._selected_date(), parent=self)
        if dlg.exec():
            self.store.appointments.append(dlg.result_appointment())
            self._refresh()

    def _edit(self) -> None:
        appt = self._selected_appointment()
        if appt is None:
            QMessageBox.information(
                self, "Bonzi", "Select an appointment to edit first."
            )
            return
        dlg = AppointmentDialog(appt.date, appt, parent=self)
        if dlg.exec():
            updated = dlg.result_appointment()
            appt.time = updated.time
            appt.title = updated.title
            appt.note = updated.note
            appt.reminded = False  # re-arm the reminder after an edit
            self._refresh()

    def _delete(self) -> None:
        appt = self._selected_appointment()
        if appt is None:
            QMessageBox.information(
                self, "Bonzi", "Select an appointment to delete first."
            )
            return
        confirm = QMessageBox.question(
            self, "BonziBUDDY", "Delete selected appointment?"
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.store.appointments.remove(appt)
            self._refresh()
