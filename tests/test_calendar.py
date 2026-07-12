"""Offscreen smoke test for the Calendar & Reminders feature.

Adds an appointment, round-trips the JSON store, opens the dialog, and fires a
due reminder through a stubbed ``say``. Run with::

    QT_QPA_PLATFORM=offscreen PYTHONPATH=src python tests/test_calendar.py
"""

from __future__ import annotations

import os
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from PySide6.QtWidgets import QApplication  # noqa: E402

from bonzi.runtime.calendar import (  # noqa: E402
    Appointment,
    AppointmentStore,
    CalendarDialog,
    fire_due_reminders,
    pop_due_appointments,
)


def test_store_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "appointments.json"
    store = AppointmentStore(path)
    store.appointments.append(
        Appointment(
            date=date(2026, 7, 12),
            time=time(9, 30),
            title="Dentist",
            note="Bring insurance card",
        )
    )
    store.save()
    assert path.exists()

    reloaded = AppointmentStore(path)
    reloaded.load()
    assert len(reloaded.appointments) == 1
    appt = reloaded.appointments[0]
    assert appt.title == "Dentist"
    assert appt.note == "Bring insurance card"
    assert appt.date == date(2026, 7, 12)
    assert appt.time == time(9, 30)
    assert appt.reminded is False

    # the day is reported as carrying appointments (drives calendar highlight)
    assert date(2026, 7, 12) in reloaded.dates_with_appointments()
    assert [a.title for a in reloaded.on_date(date(2026, 7, 12))] == ["Dentist"]


def test_due_reminder_fires(tmp_path: Path) -> None:
    path = tmp_path / "appointments.json"
    store = AppointmentStore(path)
    past = datetime.now() - timedelta(minutes=5)
    future = datetime.now() + timedelta(days=1)
    store.appointments.append(
        Appointment(date=past.date(), time=past.time().replace(microsecond=0),
                    title="Call the plumber")
    )
    store.appointments.append(
        Appointment(date=future.date(), time=time(9, 0), title="Not yet")
    )
    store.save()

    # reload from disk, exactly as the pet's timer does each tick
    fresh = AppointmentStore(path)
    fresh.load()

    spoken: list[str] = []
    animated: list[str] = []
    fired = fire_due_reminders(
        fresh, spoken.append, animated.append, attention="GetAttention"
    )

    assert [a.title for a in fired] == ["Call the plumber"]
    assert spoken == ["Reminder: Call the plumber"]
    assert animated == ["GetAttention"]

    # reminded flag is persisted, so it does not fire again
    assert pop_due_appointments(fresh) == []
    persisted = AppointmentStore(path)
    persisted.load()
    due_again = [a for a in persisted.appointments if a.title == "Call the plumber"]
    assert due_again and due_again[0].reminded is True


def test_dialog_opens(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])

    store = AppointmentStore(tmp_path / "appointments.json")
    store.appointments.append(
        Appointment(date=date(2026, 7, 12), time=time(14, 0), title="Meeting")
    )
    store.save()

    dlg = CalendarDialog(store)
    dlg._calendar.setSelectedDate(dlg._calendar.selectedDate())  # trigger refresh
    dlg.store.load()
    dlg._on_date_changed()

    dlg.show()
    app.processEvents()
    dlg.close()


def _main() -> int:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        test_store_roundtrip(base / "a")
        test_due_reminder_fires(base / "b")
        test_dialog_opens(base / "c")
    print("calendar smoke test: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
