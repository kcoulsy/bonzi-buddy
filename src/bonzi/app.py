"""Entry point: load Bonzi.acs and run the desktop pet."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from .acs import parse_acs
from .resources import asset
from .runtime.pet import BonziPet

DEFAULT_ACS = asset("Bonzi.acs")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    acs_path = Path(argv[1]) if len(argv) > 1 else DEFAULT_ACS
    if not acs_path.exists():
        print(f"Character file not found: {acs_path}", file=sys.stderr)
        return 2

    app = QApplication(argv)
    app.setApplicationName("Bonzi")
    app.setQuitOnLastWindowClosed(False)

    char = parse_acs(acs_path.read_bytes())
    pet = BonziPet(char)
    pet.quit_requested.connect(app.quit)
    # quiesce timers/audio before Qt tears down, else shutdown can crash
    app.aboutToQuit.connect(pet.cleanup)
    pet.enter()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
