"""Persistent user settings via QSettings (native store on each OS)."""

from __future__ import annotations

from PySide6.QtCore import QSettings

from .balloon import DEFAULT_BALLOON_THEME
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

    # -- character selection --

    @property
    def character_path(self) -> str:
        """Absolute path of the last-selected ``.acs`` character ("" = unset)."""
        return str(self._s.value("character_path", ""))

    @character_path.setter
    def character_path(self, v: str) -> None:
        self._s.setValue("character_path", v)

    @property
    def character_dir(self) -> str:
        """Optional extra directory scanned for user ``.acs`` files ("" = none)."""
        return str(self._s.value("character_dir", ""))

    @character_dir.setter
    def character_dir(self, v: str) -> None:
        self._s.setValue("character_dir", v)

    # -- appearance --

    @property
    def balloon_theme(self) -> str:
        """Key of the selected speech-balloon accent theme."""
        return str(self._s.value("balloon_theme", DEFAULT_BALLOON_THEME))

    @balloon_theme.setter
    def balloon_theme(self, v: str) -> None:
        self._s.setValue("balloon_theme", v)

    @property
    def first_run(self) -> bool:
        return self._s.value("first_run", True, type=bool)

    @first_run.setter
    def first_run(self, v: bool) -> None:
        self._s.setValue("first_run", bool(v))

    # -- Download Manager options (mirrors DMOptions.cs) --

    @property
    def dm_prompt_folder(self) -> bool:
        """Prompt for a destination folder before each download (ShowFilePrompt)."""
        return self._s.value("dm_prompt_folder", False, type=bool)

    @dm_prompt_folder.setter
    def dm_prompt_folder(self, v: bool) -> None:
        self._s.setValue("dm_prompt_folder", bool(v))

    @property
    def dm_run_on_complete(self) -> bool:
        """Launch a downloaded file when it finishes (RunOnComplete).

        Defaults to False for safety and only ever applies to files the user
        added and downloaded themselves.
        """
        return self._s.value("dm_run_on_complete", False, type=bool)

    @dm_run_on_complete.setter
    def dm_run_on_complete(self, v: bool) -> None:
        self._s.setValue("dm_run_on_complete", bool(v))
