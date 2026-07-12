"""Playback of the character's embedded WAV sounds (frame-triggered gags).

The .acs sounds are standard RIFF/WAV. We write them to a temp dir once and
play them with QSoundEffect (low-latency, cross-platform, no extra codecs).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from PySide6.QtCore import QObject, QUrl
from PySide6.QtMultimedia import QSoundEffect


class SoundBank(QObject):
    def __init__(self, sounds: list[bytes], parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._dir = Path(tempfile.mkdtemp(prefix="bonzi-snd-"))
        self._effects: dict[int, QSoundEffect] = {}
        self._sounds = sounds

    def _effect(self, index: int) -> QSoundEffect | None:
        if not (0 <= index < len(self._sounds)):
            return None
        eff = self._effects.get(index)
        if eff is None:
            path = self._dir / f"{index}.wav"
            if not path.exists():
                path.write_bytes(self._sounds[index])
            eff = QSoundEffect(self)
            eff.setSource(QUrl.fromLocalFile(str(path)))
            self._effects[index] = eff
        return eff

    def play(self, index: int) -> None:
        eff = self._effect(index)
        if eff is not None:
            eff.play()

    def stop_all(self) -> None:
        for eff in self._effects.values():
            eff.stop()
