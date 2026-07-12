"""Bonzi's spoken content (jokes, facts) and SAPI-markup cleanup.

The original stored lines with Microsoft SAPI inline tags like ``\\pau=2000\\``
(pause, ms) and ``\\emp\\`` (emphasis). We strip those to plain text, turning
pauses into an ellipsis beat that reads well in the balloon and via espeak.
"""

from __future__ import annotations

import json
import random
import re
from functools import lru_cache

from .resources import asset

_PAUSE = re.compile(r"\\pau=\d+\\")
_TAG = re.compile(r"\\[a-zA-Z]+(?:=[^\\]*)?\\")
_WS = re.compile(r"\s+")


def clean_markup(text: str) -> str:
    text = _PAUSE.sub("… ", text)
    text = _TAG.sub("", text)
    return _WS.sub(" ", text).strip()


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
