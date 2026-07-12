"""Persistent user settings via QSettings (native store on each OS)."""

from __future__ import annotations

from PySide6.QtCore import QSettings

from .features import DEFAULT_ENGINE


class Settings:
    def __init__(self) -> None:
        self._s = QSettings("tmafe", "BonziLinux")

    @property
    def name(self) -> str:
        return str(self._s.value("name", "friend"))

    @name.setter
    def name(self, v: str) -> None:
        self._s.setValue("name", v)

    @property
    def search_engine(self) -> str:
        return str(self._s.value("search_engine", DEFAULT_ENGINE))

    @search_engine.setter
    def search_engine(self, v: str) -> None:
        self._s.setValue("search_engine", v)

    @property
    def tts_enabled(self) -> bool:
        return self._s.value("tts_enabled", True, type=bool)

    @tts_enabled.setter
    def tts_enabled(self, v: bool) -> None:
        self._s.setValue("tts_enabled", bool(v))

    @property
    def first_run(self) -> bool:
        return self._s.value("first_run", True, type=bool)

    @first_run.setter
    def first_run(self, v: bool) -> None:
        self._s.setValue("first_run", bool(v))
