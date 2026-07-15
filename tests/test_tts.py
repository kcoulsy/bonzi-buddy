"""Tests for platform TTS command construction."""

from __future__ import annotations

import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from bonzi.runtime.tts import _windows_speech_command  # noqa: E402


def test_windows_speech_command_encodes_text_safely() -> None:
    text = "Welcome back, friend's song: \u266a Ida \u266a"

    command = _windows_speech_command("powershell.exe", text)

    assert command[:3] == ["powershell.exe", "-NoProfile", "-EncodedCommand"]
    script = base64.b64decode(command[3]).decode("utf-16le")
    assert "$s.Speak('Welcome back, friend''s song: \u266a Ida \u266a')" in script
