"""Playback of the character's embedded WAV sounds (frame-triggered gags).

The .acs sounds are standard RIFF/WAV. We write them to a temp dir and preload
them all into QSoundEffect at startup. QSoundEffect loads asynchronously, so a
play() that arrives before the clip is Ready is deferred until it finishes
loading (otherwise that first play is silently dropped — the cause of "only one
sound ever plays").
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
        self._pending: set[int] = set()
        for i, wav in enumerate(sounds):
            if not wav:
                continue
            path = self._dir / f"{i}.wav"
            path.write_bytes(wav)
            eff = QSoundEffect(self)
            eff.setSource(QUrl.fromLocalFile(str(path)))
            eff.statusChanged.connect(lambda idx=i: self._on_status(idx))
            self._effects[i] = eff

    def _on_status(self, index: int) -> None:
        eff = self._effects.get(index)
        if eff is not None and eff.isLoaded() and index in self._pending:
            self._pending.discard(index)
            eff.play()

    def play(self, index: int) -> None:
        eff = self._effects.get(index)
        if eff is None:
            return
        if eff.isLoaded():
            eff.play()
        else:
            # clip still loading — play it as soon as it's ready
            self._pending.add(index)

    def stop_all(self) -> None:
        self._pending.clear()
        for eff in self._effects.values():
            eff.stop()
