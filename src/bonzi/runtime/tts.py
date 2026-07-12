"""Text-to-speech via a Linux CLI engine (espeak-ng / espeak / spd-say).

Runs the engine in a worker thread so the UI never blocks, and reports start/end
so the character can gesture while it talks. Voice pitch/speed are seeded from
the .acs voice block to approximate Bonzi's original delivery.
"""

from __future__ import annotations

import shutil
import subprocess

from PySide6.QtCore import QObject, QThread, Signal

from ..acs.model import Voice


def _find_engine() -> list[str] | None:
    """Return a base command (without text) for the first available engine."""
    if shutil.which("espeak-ng"):
        return ["espeak-ng"]
    if shutil.which("espeak"):
        return ["espeak"]
    if shutil.which("spd-say"):
        return ["spd-say", "-w"]  # -w: wait for playback to finish
    return None


class _SpeakWorker(QThread):
    def __init__(self, cmd: list[str], text: str) -> None:
        super().__init__()
        self._cmd = cmd
        self._text = text

    def run(self) -> None:
        try:
            subprocess.run([*self._cmd, self._text], check=False)
        except Exception:
            pass


class TtsEngine(QObject):
    started = Signal()
    stopped = Signal()

    def __init__(self, voice: Voice | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._base = _find_engine()
        self._worker: _SpeakWorker | None = None
        self._extra = self._voice_args(voice)

    @property
    def available(self) -> bool:
        return self._base is not None

    def _voice_args(self, voice: Voice | None) -> list[str]:
        if not self._base or self._base[0] not in ("espeak-ng", "espeak") or voice is None:
            return []
        args: list[str] = []
        # .acs pitch/speed are SAPI-ish 0..200ish; map loosely into espeak ranges.
        if voice.pitch is not None:
            args += ["-p", str(max(0, min(99, voice.pitch // 2)))]
        if voice.speed is not None:
            args += ["-s", str(max(80, min(260, voice.speed)))]
        return args

    def speak(self, text: str) -> None:
        text = text.strip()
        if not text or not self._base:
            return
        self.stop()
        worker = _SpeakWorker([*self._base, *self._extra], text)
        worker.started.connect(self.started.emit)
        worker.finished.connect(self._on_finished)
        self._worker = worker
        worker.start()

    def stop(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.terminate()
            self._worker.wait(200)
        self._worker = None

    def _on_finished(self) -> None:
        self._worker = None
        self.stopped.emit()
