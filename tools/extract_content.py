"""One-off: pull Bonzi's joke & fact banks out of the decompiled source into
committed JSON data (so the app doesn't depend on the decompiled tree).

    python tools/extract_content.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

SRC = Path("decompiled/BonziRW/BonziBUDDYRW/BonziWORLD.cs")
OUT = Path("assets")

SPEAK_RE = re.compile(r'Bonzi\.Speak\(\(object\)"((?:[^"\\]|\\.)*)"')
CASE_RE = re.compile(r"^\s*case \d+:")


def unescape_csharp(s: str) -> str:
    return s.encode("latin-1", "backslashreplace").decode("unicode_escape", "ignore") \
        if False else s.replace('\\"', '"').replace("\\\\", "\\")


def method_body(text: str, name: str) -> str:
    start = text.index(f"private void {name}()")
    # crude brace-matching from the first '{' after the signature
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


def extract_cases(body: str) -> list[str]:
    """Group consecutive Speak() strings within each `case N:` into one entry."""
    entries: list[str] = []
    current: list[str] | None = None
    for line in body.splitlines():
        if CASE_RE.match(line):
            if current:
                entries.append(" ".join(current))
            current = []
        m = SPEAK_RE.search(line)
        if m is not None and current is not None:
            current.append(unescape_csharp(m.group(1)))
    if current:
        entries.append(" ".join(current))
    # de-dupe while preserving order; drop empties
    seen: set[str] = set()
    out: list[str] = []
    for e in entries:
        e = e.strip()
        if e and e not in seen:
            seen.add(e)
            out.append(e)
    return out


def main() -> int:
    text = SRC.read_text(encoding="utf-8")
    jokes = extract_cases(method_body(text, "JokeMain"))
    facts = extract_cases(method_body(text, "FactMain"))
    (OUT / "jokes.json").write_text(json.dumps(jokes, indent=1, ensure_ascii=False))
    (OUT / "facts.json").write_text(json.dumps(facts, indent=1, ensure_ascii=False))
    print(f"jokes: {len(jokes)}  facts: {len(facts)}")
    print("sample joke:", jokes[0] if jokes else "-")
    print("sample fact:", facts[0] if facts else "-")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
