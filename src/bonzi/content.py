"""Bonzi's spoken content (jokes, facts) and SAPI-markup cleanup.

The original stored lines with Microsoft SAPI inline tags like ``\\pau=2000\\``
(pause, ms) and ``\\emp\\`` (emphasis). We strip those to plain text, turning
pauses into an ellipsis beat that reads well in the balloon and via espeak.
"""

from __future__ import annotations

import json
import random
import re
import statistics
from functools import lru_cache
from xml.sax.saxutils import escape as xml_escape

from .resources import asset

_PAUSE = re.compile(r"\\pau=\d+\\")
_TAG = re.compile(r"\\[a-zA-Z]+(?:=[^\\]*)?\\")
_WS = re.compile(r"\s+")
# SAPI song lines use \Map="phonetic"="readable"\ — the 2nd part is clean lyric.
_MAP = re.compile(r'\\Map="[^"]*"="([^"]*)"\\', re.IGNORECASE)
# The sung (pitch-bearing) half of a Map tag: \Map="<this>"="display"\
_MAP_SUNG = re.compile(r'\\Map="([^"]*)"="[^"]*"\\', re.IGNORECASE)
# A single SAPI inline tag: \name=value\ or \name="value"\
_SAPI_TOKEN = re.compile(r'\\([A-Za-z]+)=("?)(.*?)\2\\')


def clean_markup(text: str) -> str:
    text = _PAUSE.sub("… ", text)
    text = _TAG.sub("", text)
    return _WS.sub(" ", text).strip()


def clean_lyric(line: str) -> str:
    """Human-readable lyric from a SAPI song line (prefers Map display text)."""
    line = _MAP.sub(lambda m: m.group(1), line)
    return clean_markup(line)


@lru_cache(maxsize=None)
def _load(name: str) -> tuple[str, ...]:
    path = asset(name)
    if not path.exists():
        return ()
    return tuple(clean_markup(s) for s in json.loads(path.read_text(encoding="utf-8")))


def jokes() -> tuple[str, ...]:
    return _load("jokes.json")


def facts() -> tuple[str, ...]:
    return _load("facts.json")


def random_joke() -> str:
    pool = jokes()
    return random.choice(pool) if pool else "I forgot my joke book!"


def random_fact() -> str:
    pool = facts()
    return random.choice(pool) if pool else "Did you know I run natively on Linux now?"


@lru_cache(maxsize=1)
def songs() -> tuple[dict, ...]:
    path = asset("songs.json")
    if not path.exists():
        return ()
    return tuple(json.loads(path.read_text(encoding="utf-8")))


def random_song() -> dict | None:
    pool = songs()
    return random.choice(pool) if pool else None


def song_lyrics(song: dict) -> str:
    """Full readable lyric text for a song."""
    return " ".join(clean_lyric(ln) for ln in song.get("lines", []) if ln.strip())


def _sung_segment(line: str) -> str:
    """The pitch-bearing text of a line (inside \\Map=... if present)."""
    m = _MAP_SUNG.search(line)
    return m.group(1) if m else line


def song_to_ssml(song: dict) -> tuple[str, int]:
    """Convert a song's SAPI pitch markup into espeak-ng SSML + a base speed.

    Microsoft Agent's ``\\Pit=N\\`` is the voice fundamental frequency in Hz, so
    each syllable maps straight onto ``<prosody pitch="NHz">`` — reproducing the
    original melody contour. ``\\Spd=N\\`` (words per minute) becomes the base
    espeak rate (we take the song's median so espeak can vary around it).
    """
    speeds: list[int] = []
    parts: list[str] = []
    for raw in song.get("lines", []):
        seg = _sung_segment(raw)
        pitch: int | None = None
        pieces: list[str] = []
        pos = 0
        for tok in _SAPI_TOKEN.finditer(seg):
            _emit(pieces, seg[pos:tok.start()], pitch)
            name, val = tok.group(1).lower(), tok.group(3)
            if name == "pit" and val.isdigit():
                pitch = int(val)
            elif name == "spd" and val.isdigit():
                speeds.append(int(val))
            pos = tok.end()
        _emit(pieces, seg[pos:], pitch)
        if pieces:
            parts.append("".join(pieces))
    ssml = '<speak>' + ' <break time="90ms"/> '.join(parts) + "</speak>"
    speed = int(statistics.median(speeds)) if speeds else 130
    return ssml, max(80, min(260, speed))


def song_performance(song: dict) -> tuple[str, str, int]:
    """Return (balloon_text, ssml, wpm) for singing a song.

    The SSML opens with a spoken (natural-pitch) intro, then the sung melody.
    """
    lyrics = song_lyrics(song)
    ssml, wpm = song_to_ssml(song)
    intro = f"Here's {song.get('title', 'a song')}, by {song.get('author', 'a friend')}."
    ssml = ssml.replace(
        "<speak>", f'<speak>{xml_escape(intro)} <break time="400ms"/> ', 1
    )
    display = f"♪ {song.get('title', 'A song')} ♪  {lyrics}"
    return display, ssml, wpm


def _emit(pieces: list[str], text: str, pitch: int | None) -> None:
    text = text.strip()
    if not text:
        return
    safe = xml_escape(text)
    if pitch:
        pieces.append(f'<prosody pitch="{pitch}Hz">{safe}</prosody> ')
    else:
        pieces.append(safe + " ")
