"""A small Options dialog (name, default search engine, voice toggle)."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
)

from .balloon import BALLOON_THEMES
from .features import SEARCH_ENGINES
from .settings import Settings


class OptionsDialog(QDialog):
    def __init__(self, settings: Settings, tts_available: bool, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Bonzi Options")
        self._s = settings

        self._name = QLineEdit(settings.name)
        self._engine = QComboBox()
        self._engine.addItems(list(SEARCH_ENGINES))
        self._engine.setCurrentText(settings.search_engine)
        self._tts = QCheckBox("Speak out loud (text-to-speech)")
        self._tts.setChecked(settings.tts_enabled)
        self._tts.setEnabled(tts_available)
        if not tts_available:
            self._tts.setText("Speak out loud — install espeak-ng to enable")

        self._balloon = QComboBox()
        for theme in BALLOON_THEMES.values():
            self._balloon.addItem(theme.label, theme.key)
        idx = self._balloon.findData(settings.balloon_theme)
        self._balloon.setCurrentIndex(idx if idx >= 0 else 0)

        form = QFormLayout(self)
        form.addRow("Your name:", self._name)
        form.addRow("Search engine:", self._engine)
        form.addRow("Balloon style:", self._balloon)
        form.addRow(self._tts)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _save(self) -> None:
        name = self._name.text().strip()
        if name:
            self._s.name = name
        self._s.search_engine = self._engine.currentText()
        self._s.balloon_theme = self._balloon.currentData()
        self._s.tts_enabled = self._tts.isChecked()
        self.accept()
