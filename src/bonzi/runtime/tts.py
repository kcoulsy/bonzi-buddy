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
    """Waits for an already-started engine process so the UI never blocks.

    The process is created by :meth:`TtsEngine.speak` on the caller's thread, so
    it always exists by the time :meth:`stop_process` may need to kill it.
    """

    def __init__(self, proc: subprocess.Popen) -> None:
        super().__init__()
        self._proc = proc

    def run(self) -> None:
        try:
            self._proc.wait()
        except Exception:
            pass

    def stop_process(self) -> None:
        """Kill the engine so its audio stops immediately."""
        proc = self._proc
        if proc.poll() is not None:
            return
        try:
            proc.terminate()
            try:
                proc.wait(0.2)
            except subprocess.TimeoutExpired:
                proc.kill()
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

    @property
    def supports_ssml(self) -> bool:
        """espeak(-ng) can render the SSML we use to sing melodies."""
        return bool(self._base) and self._base[0] in ("espeak-ng", "espeak")

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
        self._launch([*self._base, *self._extra, text])

    def sing(self, ssml: str, wpm: int) -> None:
        """Sing an SSML document (per-syllable pitch) via espeak-ng SSML mode."""
        if not self.supports_ssml:
            return
        self._launch([*self._base, "-m", "-s", str(wpm), ssml])

    def _launch(self, cmd: list[str]) -> None:
        self.stop()
        try:
            proc = subprocess.Popen(cmd)
        except Exception:
            return
        worker = _SpeakWorker(proc)
        worker.started.connect(self.started.emit)
        worker.finished.connect(self._on_finished)
        self._worker = worker
        worker.start()

    def stop(self) -> None:
        if self._worker is not None:
            # Kill the engine process first, then let run() return and join.
            self._worker.stop_process()
            if self._worker.isRunning():
                self._worker.wait(300)
        self._worker = None

    def _on_finished(self) -> None:
        # Ignore the tail of a worker we already replaced/stopped, so it can't
        # null out the current worker or hide a fresh balloon.
        if self.sender() is not self._worker:
            return
        self._worker = None
        self.stopped.emit()
