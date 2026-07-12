"""Text-to-speech via platform-native or CLI engines.

Runs the engine in a worker thread so the UI never blocks, and reports start/end
so the character can gesture while it talks. Voice pitch/speed are seeded from
the .acs voice block to approximate Bonzi's original delivery.

Supported engines (checked in order):
  Linux   – espeak-ng, espeak, spd-say
  macOS   – say (built-in)
  Windows – PowerShell + System.Speech (built-in)
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

from PySide6.QtCore import QObject, QThread, Signal

from ..acs.model import Voice


def _subprocess_env() -> dict[str, str] | None:
    """Environment for spawning the TTS engine.

    When frozen by PyInstaller, the app runs with ``LD_LIBRARY_PATH`` (and
    related vars) pointed at its bundled libraries. A system engine like
    espeak-ng inherits that and loads the *bundled* libstdc++/libpulse/etc.,
    which are usually incompatible — the process launches but produces no audio.
    PyInstaller stashes the pre-launch values under an ``*_ORIG`` suffix, so we
    restore them (or drop the var entirely) for the child process.
    """
    if not getattr(sys, "frozen", False):
        return None  # running from source: inherit the real environment
    env = dict(os.environ)
    for var in ("LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH", "DYLD_FRAMEWORK_PATH"):
        orig = env.get(f"{var}_ORIG")
        if orig is not None:
            env[var] = orig
        else:
            env.pop(var, None)
    return env


def _find_player() -> list[str] | None:
    """Return a command that plays a WAV stream from stdin, if one exists.

    espeak(-ng)'s built-in audio output (via pcaudiolib) is silent on some
    systems — the process runs for the right duration but no sound comes out.
    Rendering to a WAV on stdout and piping it into a dedicated player sidesteps
    that entirely and is far more reliable on PulseAudio/PipeWire desktops.
    """
    for cmd in (["paplay"], ["pw-play"], ["aplay", "-q"]):
        if shutil.which(cmd[0]):
            return cmd
    return None


def _find_engine() -> list[str] | None:
    """Return a base command (without text) for the first available engine."""
    if sys.platform == "win32":
        ps = shutil.which("powershell")
        if ps:
            return [
                ps,
                "-NoProfile",
                "-Command",
                "Add-Type -AssemblyName System.Speech;"
                "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
                "$s.Speak([System.IO.File]::ReadAllText($args[0]))",
            ]
        return None

    if sys.platform == "darwin":
        if shutil.which("say"):
            return ["say"]
        return None

    # Linux
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

    def __init__(self, procs: list[subprocess.Popen]) -> None:
        super().__init__()
        # procs[0] is the tail of the pipeline (the audio player, or the engine
        # itself when playing directly) — it finishes when playback is done.
        self._procs = procs

    def run(self) -> None:
        try:
            self._procs[0].wait()
        except Exception:
            pass

    def stop_process(self) -> None:
        """Kill every process in the pipeline so audio stops immediately."""
        for proc in self._procs:
            if proc.poll() is not None:
                continue
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
        self._player = _find_player()
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
        procs = self._spawn(cmd)
        if not procs:
            return
        worker = _SpeakWorker(procs)
        worker.started.connect(self.started.emit)
        worker.finished.connect(self._on_finished)
        self._worker = worker
        worker.start()

    def _spawn(self, cmd: list[str]) -> list[subprocess.Popen]:
        """Start the engine, piping its WAV into a player when possible."""
        env = _subprocess_env()
        pipe = self._player is not None and bool(cmd) and cmd[0] in ("espeak-ng", "espeak")
        try:
            if pipe:
                # Render to stdout as WAV and pipe into the player, instead of
                # trusting espeak's (often silent) built-in audio output.
                engine = subprocess.Popen(
                    [cmd[0], "--stdout", *cmd[1:]], stdout=subprocess.PIPE, env=env
                )
                player = subprocess.Popen(self._player, stdin=engine.stdout, env=env)
                if engine.stdout is not None:
                    engine.stdout.close()
                return [player, engine]
            return [subprocess.Popen(cmd, env=env)]
        except Exception:
            return []

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
