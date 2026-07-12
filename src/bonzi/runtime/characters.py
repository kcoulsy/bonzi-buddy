"""Discover and load Microsoft Agent characters (``.acs`` files).

BonziBUDDY ships one character (Bonzi) but the on-screen pet can host any
Microsoft Agent v2 ``.acs`` file. Characters live under ``assets/characters/``
plus an optional user directory; each file decodes to a :class:`Character` the
pet can swap to at runtime, with the choice persisted in QSettings.

Parsing a character is expensive (Bonzi.acs is ~5 MB), so :func:`load_character`
caches by resolved-path identity. The pet seeds the cache with the character it
is already running, so building the "Characters" menu only pays to parse files
the user has not yet loaded.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..acs import parse_acs
from ..acs.model import Character
from ..resources import asset


def characters_root() -> Path:
    """Directory that holds one ``.acs`` file per bundled character."""
    return asset("characters")


# resolved-path -> (mtime, size, parsed Character); avoids reparsing 5 MB files
_parse_cache: dict[Path, tuple[float, int, Character]] = {}


def load_character(path: Path) -> Character:
    """Parse ``path`` into a :class:`Character`, cached by file identity.

    Raises whatever :func:`~bonzi.acs.parse_acs` raises for a malformed file;
    callers that enumerate untrusted directories should guard the call.
    """
    path = Path(path)
    key = path.resolve()
    st = path.stat()
    cached = _parse_cache.get(key)
    if cached is not None and cached[0] == st.st_mtime and cached[1] == st.st_size:
        return cached[2]
    char = parse_acs(path.read_bytes())
    _parse_cache[key] = (st.st_mtime, st.st_size, char)
    return char


@dataclass(frozen=True)
class CharacterEntry:
    """A discovered character file and its display name (for menus)."""

    path: Path
    name: str


def discover_paths(extra_dir: Path | None = None) -> list[Path]:
    """All ``.acs`` files under the bundled dir plus an optional user dir.

    Deduplicated by resolved path and sorted by filename. Missing or unreadable
    directories are skipped, so a fresh install with no characters folder — or a
    bad user path — still returns whatever else is available.
    """
    dirs = [characters_root()]
    if extra_dir is not None:
        dirs.append(Path(extra_dir))
    seen: set[Path] = set()
    out: list[Path] = []
    for d in dirs:
        try:
            files = sorted(d.glob("*.acs"))
        except OSError:
            continue
        for f in files:
            resolved = f.resolve()
            if resolved in seen or not f.is_file():
                continue
            seen.add(resolved)
            out.append(f)
    return out


def entry_name(path: Path) -> str:
    """Display name for a character file: its ACS name, else the file stem."""
    try:
        char = load_character(path)
    except Exception:
        return path.stem
    return char.name or path.stem


def discover(extra_dir: Path | None = None) -> list[CharacterEntry]:
    """Discovered characters as name-bearing entries for the menu."""
    return [CharacterEntry(p, entry_name(p)) for p in discover_paths(extra_dir)]


def initial_character_path(saved: str = "", extra_dir: Path | None = None) -> Path | None:
    """The character to load on startup.

    Prefers the persisted choice (if it still exists), then the first discovered
    character, then the pre-move ``assets/Bonzi.acs`` for backwards
    compatibility. Returns ``None`` only when nothing is available.
    """
    if saved:
        p = Path(saved)
        if p.exists():
            return p
    paths = discover_paths(extra_dir)
    if paths:
        return paths[0]
    legacy = asset("Bonzi.acs")  # location before characters/ existed
    return legacy if legacy.exists() else None
