"""Dataclasses describing a parsed Microsoft Agent character."""

from __future__ import annotations

from dataclasses import dataclass, field

Rgb = tuple[int, int, int]


@dataclass
class Image:
    """One decoded sprite: top-down RGBA with the transparent index keyed out."""

    width: int
    height: int
    rgba: bytes  # width*height*4, top-down, straight alpha


@dataclass
class FrameImage:
    image_index: int
    x: int
    y: int


@dataclass
class FrameBranch:
    frame_index: int
    probability: int  # 0..100


@dataclass
class MouthOverlay:
    type: int
    replace_flag: bool
    image_index: int
    x: int
    y: int
    rgn_flag: int
    scale_x: int
    scale_y: int


@dataclass
class Frame:
    images: list[FrameImage]
    duration_ms: int
    branches: list[FrameBranch] = field(default_factory=list)
    exit_frame: int | None = None
    sound_index: int | None = None
    mouth_overlays: list[MouthOverlay] = field(default_factory=list)


@dataclass
class Animation:
    name: str
    transition_type: int  # 1 = exit-branching, 2 = none, else return_animation
    frames: list[Frame]
    return_animation: str | None = None


@dataclass
class Voice:
    speed: int | None = None
    pitch: int | None = None
    language_id: int | None = None
    gender_code: int | None = None
    age: int | None = None


@dataclass
class Balloon:
    num_lines: int
    chars_per_line: int
    font_name: str
    font_height: int
    fg: Rgb
    bg: Rgb
    border: Rgb


@dataclass
class Character:
    guid: str
    name: str | None
    width: int
    height: int
    transparent_index: int
    palette: list[Rgb]
    images: list[Image]
    animations: list[Animation]
    sounds: list[bytes]  # raw WAV bytes
    voice: Voice
    balloon: Balloon | None
    states: dict[str, list[str]]

    def animation(self, name: str) -> Animation | None:
        lower = name.lower()
        for a in self.animations:
            if a.name.lower() == lower:
                return a
        return None
