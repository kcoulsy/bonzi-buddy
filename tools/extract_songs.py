"""One-off: extract Bonzi's 20 songs (title, author, sung lines with SAPI pitch
markup) from the decompiled source into committed JSON.

    python tools/extract_songs.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

WORLD = Path("decompiled/BonziRW/BonziBUDDYRW/BonziWORLD.cs")
SING = Path("decompiled/BonziRW/BonziBUDDYRW/BonziSing.cs")
OUT = Path("assets/songs.json")

SPEAK_RE = re.compile(r'Bonzi\.Speak\(\(object\)"((?:[^"\\]|\\.)*)"')
CASE_RE = re.compile(r"^\s*case (\d+):")
ITEM_RE = re.compile(r'new string\[2\]\s*\{\s*"([^"]+)",\s*"([^"]+)"\s*\}')
TAG_RE = re.compile(r"val(\d*)\.Tag = \"(\d+)\";")


def unescape(s: str) -> str:
    return s.replace('\\"', '"').replace("\\\\", "\\")


def method_body(text: str, sig: str) -> str:
    start = text.index(sig)
    i = text.index("{", start)
    depth = 0
    for j in range(i, len(text)):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return text[i : j + 1]
    return text[i:]


def song_titles() -> dict[int, tuple[str, str]]:
    """Map SongId -> (title, author) using the playlist items and their tags."""
    text = SING.read_text(encoding="utf-8")
    items = ITEM_RE.findall(text)  # in val1..val20 order
    tags: dict[int, int] = {}  # item ordinal (1-based) -> SongId
    for ordinal, songid in TAG_RE.findall(text):
        idx = int(ordinal) if ordinal else 1
        tags[idx] = int(songid)
    out: dict[int, tuple[str, str]] = {}
    for i, (title, author) in enumerate(items, start=1):
        songid = tags.get(i)
        if songid:
            out[songid] = (title, author)
    return out


def songs_by_id() -> dict[int, list[str]]:
    body = method_body(WORLD.read_text(encoding="utf-8"), "void SingMain")
    songs: dict[int, list[str]] = {}
    cur: int | None = None
    for line in body.splitlines():
        m = CASE_RE.match(line)
        if m:
            cur = int(m.group(1))
            songs[cur] = []
        s = SPEAK_RE.search(line)
        if s and cur is not None:
            txt = unescape(s.group(1))
            if txt.strip():
                songs[cur].append(txt)
    return songs


def main() -> int:
    titles = song_titles()
    lines = songs_by_id()
    out = []
    for songid in sorted(lines):
        title, author = titles.get(songid, (f"Song {songid}", "Unknown"))
        out.append({"id": songid, "title": title, "author": author, "lines": lines[songid]})
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(f"songs: {len(out)}")
    for s in out[:3]:
        print(f"  {s['id']:2} {s['title']} — {s['author']} ({len(s['lines'])} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
