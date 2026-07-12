"""Locate bundled assets in both a source checkout and a frozen build.

PyInstaller unpacks data files under ``sys._MEIPASS``; a normal checkout keeps
them in the repo's top-level ``assets/`` directory.
"""

from __future__ import annotations

import sys
from pathlib import Path


def resource_root() -> Path:
    """Directory that contains the ``assets/`` folder."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent.parent


def asset(*parts: str) -> Path:
    return resource_root().joinpath("assets", *parts)
