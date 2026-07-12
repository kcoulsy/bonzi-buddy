"""Entry point: load a character and run the desktop pet.

The character is chosen at startup (CLI argument, persisted choice, or the first
one discovered under ``assets/characters/``) and can be swapped at runtime from
the pet's "Characters" menu. :class:`PetController` owns the live pet so a swap
can dispose the old widget and rebuild a fresh one against the new character.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Desktop pets need absolute window positioning, which the Wayland protocol
# deliberately does not provide. Use XWayland on Linux unless the user opted
# into a Qt platform backend explicitly.
if sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

from PySide6.QtWidgets import QApplication

from .runtime.characters import initial_character_path, load_character
from .runtime.pet import BonziPet
from .runtime.settings import Settings


class PetController:
    """Owns the on-screen pet and rebuilds it when the user picks a character."""

    def __init__(self, app: QApplication, settings: Settings | None = None) -> None:
        self.app = app
        self.settings = settings or Settings()
        self.pet: BonziPet | None = None

    def _make(self, path: Path) -> BonziPet:
        """Parse ``path`` and wire a fresh pet to the app (may raise on a bad file)."""
        char = load_character(path)
        pet = BonziPet(char, source_path=path)
        pet.quit_requested.connect(self.app.quit)
        pet.switch_requested.connect(self.switch)
        return pet

    def start(self, path: Path) -> None:
        self.pet = self._make(path)
        self.pet.enter()

    def switch(self, path_str: str) -> None:
        """Swap to the character at ``path_str``, disposing the old pet cleanly.

        A malformed/missing file leaves the current pet untouched (and, if one is
        running, has it apologise) rather than tearing everything down.
        """
        path = Path(path_str)
        try:
            new = self._make(path)
        except Exception as exc:  # bad signature, unreadable file, etc.
            if self.pet is not None:
                self.pet.say("Sorry, I couldn't load that character.")
            print(f"Failed to load character {path}: {exc}", file=sys.stderr)
            return

        old = self.pet
        if old is not None:
            new.move(old.pos())  # keep the pet where the user left it
        self.settings.character_path = str(path)
        self.pet = new
        new.enter(greeting=f"Hi! I'm {new.char.name or 'your new buddy'} now.")
        if old is not None:
            old.switch_requested.disconnect()
            old.quit_requested.disconnect()
            old.dispose()
            old.close()
            old.deleteLater()

    def cleanup(self) -> None:
        """Quiesce the live pet before Qt tears down (wired to aboutToQuit)."""
        if self.pet is not None:
            self.pet.cleanup()


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)

    app = QApplication(argv)
    app.setApplicationName("Bonzi")
    app.setQuitOnLastWindowClosed(False)

    settings = Settings()
    extra = settings.character_dir
    if len(argv) > 1:
        acs_path: Path | None = Path(argv[1])
    else:
        acs_path = initial_character_path(
            settings.character_path, Path(extra) if extra else None
        )
    if acs_path is None or not acs_path.exists():
        print(f"Character file not found: {acs_path}", file=sys.stderr)
        return 2

    controller = PetController(app, settings)
    # quiesce timers/audio before Qt tears down, else shutdown can crash
    app.aboutToQuit.connect(controller.cleanup)
    controller.start(acs_path)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
