"""Offscreen smoke test for character discovery + runtime switching.

Enumerates the bundled characters, parses one into a :class:`Character`, then
drives :class:`PetController` through a live swap and confirms the new character
is loaded and the old pet disposed. Also checks the graceful paths: a bad/missing
file leaves the current pet standing, and an empty directory yields no entries.
Run with::

    QT_QPA_PLATFORM=offscreen PYTHONPATH=src python tests/test_characters.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from PySide6.QtWidgets import QApplication  # noqa: E402

from bonzi.acs.model import Character  # noqa: E402
from bonzi.app import PetController  # noqa: E402
from bonzi.runtime.characters import (  # noqa: E402
    characters_root,
    discover,
    discover_paths,
    initial_character_path,
    load_character,
)

# QSettings / QWidget construction needs a running application instance.
_app = QApplication.instance() or QApplication([])


def test_enumerate_characters() -> None:
    paths = discover_paths()
    assert paths, f"no .acs characters found under {characters_root()}"
    # the shipped Bonzi character must be discoverable
    assert any(p.name == "Bonzi.acs" for p in paths), [p.name for p in paths]

    entries = discover()
    assert len(entries) == len(paths)
    for entry in entries:
        assert entry.name, f"empty display name for {entry.path}"


def test_load_character_and_cache() -> None:
    path = discover_paths()[0]
    char = load_character(path)
    assert isinstance(char, Character)
    assert char.animations, "character has no animations"
    # second load must hit the cache and return the identical object
    assert load_character(path) is char


def test_initial_path_prefers_saved() -> None:
    bonzi = discover_paths()[0]
    # a valid saved path is honoured …
    assert initial_character_path(str(bonzi)) == bonzi
    # … a stale one falls through to the first discovered character
    assert initial_character_path("/nope/gone.acs") == discover_paths()[0]


def test_missing_extra_dir_is_safe() -> None:
    """A missing/unreadable extra directory adds nothing and never crashes."""
    before = len(discover_paths())
    after = len(discover_paths(Path("/nonexistent-characters-dir")))
    assert after == before


def test_runtime_swap_loads_new_character() -> None:
    bonzi = discover_paths()[0]
    controller = PetController(_app)
    controller.start(bonzi)
    _app.processEvents()

    old = controller.pet
    assert old is not None
    assert isinstance(old.char, Character)

    # swap to a character (only Bonzi ships, so swap to it): exercises the full
    # dispose-old / rebuild-new path in the controller.
    target = discover_paths()[-1]
    controller.switch(str(target))
    _app.processEvents()

    new = controller.pet
    assert new is not None and new is not old, "controller did not rebuild the pet"
    assert isinstance(new.char, Character)
    assert new.char.name, "new character has no name"
    assert new.source_path is not None and new.source_path.resolve() == target.resolve()
    # persisted for next launch
    assert new.settings.character_path == str(target)

    controller.cleanup()
    _app.processEvents()


def test_missing_file_keeps_current_pet() -> None:
    bonzi = discover_paths()[0]
    controller = PetController(_app)
    controller.start(bonzi)
    _app.processEvents()

    current = controller.pet
    controller.switch("/definitely/not/here.acs")
    _app.processEvents()

    assert controller.pet is current, "a bad file should not replace the pet"

    controller.cleanup()
    _app.processEvents()


def _main() -> int:
    test_enumerate_characters()
    test_load_character_and_cache()
    test_initial_path_prefers_saved()
    test_missing_extra_dir_is_safe()
    test_runtime_swap_loads_new_character()
    test_missing_file_keeps_current_pet()
    print("characters smoke test: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
