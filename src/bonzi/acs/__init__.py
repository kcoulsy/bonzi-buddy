"""Microsoft Agent ``.acs`` character-file decoder."""

from .model import Animation, Character, Frame, Image
from .parser import parse_acs

__all__ = ["parse_acs", "Character", "Animation", "Frame", "Image"]
