"""Parser for Microsoft Agent version 2 ``.acs`` character files.

Layout (all little-endian):

    u32 signature (0xABCDABC3)
    4 x LOCATOR { u32 offset; u32 size }   # header, anim index, image index, sound index

The header block holds version, a pointer to the localized names block, the
character GUID, default width/height, the transparent palette index, a style
bitmask (bit 0x20 => TTS voice block present, 0x200 => balloon block present),
then optional voice/balloon, the palette, an optional tray icon, the state map,
and (via the names pointer) the character name.

Images, animations and sounds are each an indexed table of file offsets.
"""

from __future__ import annotations

from .image import _palette_lut
from .model import (
    Animation,
    Balloon,
    Character,
    Frame,
    FrameBranch,
    FrameImage,
    MouthOverlay,
    Rgb,
    Voice,
)
from .reader import BinaryReader
from .store import LazyImageStore

ACS_SIGNATURE = 0xABCDABC3
STYLE_TTS = 0x00000020
STYLE_BALLOON = 0x00000200
GUID_NULL = "{00000000-0000-0000-0000-000000000000}"


class Locator:
    __slots__ = ("offset", "size")

    def __init__(self, offset: int, size: int) -> None:
        self.offset = offset
        self.size = size


def parse_acs(data: bytes) -> Character:
    r = BinaryReader(data)

    sig = r.u32()
    if sig != ACS_SIGNATURE:
        raise ValueError(f"parse_acs: bad signature 0x{sig:08X} (expected 0xABCDABC3)")

    locators = [Locator(r.u32(), r.u32()) for _ in range(4)]
    header_loc, anim_loc, image_loc, sound_loc = locators

    # ---- header / character block ----
    r.seek(header_loc.offset)
    r.u16()  # version minor
    r.u16()  # version major
    names_offset = r.u32()
    r.u32()  # names size
    guid = r.guid()
    width = r.u16()
    height = r.u16()
    transparent_index = r.u8()
    style = r.u32()
    r.u32()  # unknown (== 2)

    voice = _read_voice(r) if style & STYLE_TTS else Voice()
    balloon = _read_balloon(r) if style & STYLE_BALLOON else None
    palette = _read_palette(r)
    _skip_icon(r)
    states = _read_states(r)
    name = _read_character_name(r, names_offset)

    images = _read_images(r, image_loc, palette, transparent_index)
    animations = _read_animations(r, anim_loc)
    sounds = _read_sounds(r, sound_loc)

    return Character(
        guid=guid,
        name=name,
        width=width,
        height=height,
        transparent_index=transparent_index,
        palette=palette,
        images=images,
        animations=animations,
        sounds=sounds,
        voice=voice,
        balloon=balloon,
        states=states,
    )


# --- header sub-blocks ---


def _read_color_ref(r: BinaryReader) -> Rgb:
    """A COLORREF stored B, G, R, reserved."""
    b = r.u8()
    g = r.u8()
    red = r.u8()
    r.u8()  # reserved
    return (red, g, b)


def _read_palette(r: BinaryReader) -> list[Rgb]:
    count = r.u32()
    return [_read_color_ref(r) for _ in range(count)]


def _read_balloon(r: BinaryReader) -> Balloon:
    num_lines = r.u8()
    chars_per_line = r.u8()
    fg = _read_color_ref(r)
    bg = _read_color_ref(r)
    border = _read_color_ref(r)
    font_name = r.string()
    font_height = abs(r.i32())
    r.u16()  # weight
    r.u16()  # strikeout
    r.u16()  # italic
    return Balloon(num_lines, chars_per_line, font_name, font_height, fg, bg, border)


def _skip_icon(r: BinaryReader) -> None:
    if r.u8():
        r.skip(r.u32())  # mask
        r.skip(r.u32())  # color


def _read_states(r: BinaryReader) -> dict[str, list[str]]:
    states: dict[str, list[str]] = {}
    for _ in range(r.u16()):
        name = r.string()
        states[name] = [r.string() for _ in range(r.u16())]
    return states


def _read_character_name(r: BinaryReader, names_offset: int) -> str | None:
    if not names_offset:
        return None
    r.seek(names_offset)
    chosen: str | None = None
    for _ in range(r.u16()):
        r.u16()  # language id
        name = r.string()
        r.string()  # desc1
        r.string()  # desc2
        if name and chosen is None:
            chosen = name
    return chosen


def _read_voice(r: BinaryReader) -> Voice:
    r.guid()  # engine guid
    mode_guid = r.guid()
    speed = r.i32()
    pitch = r.i16()
    voice = Voice(speed=speed, pitch=pitch)
    if r.u8():  # has language block
        voice.language_id = r.u16()
        r.string()  # lang string
        voice.gender_code = r.u16()
        voice.age = r.u16()
        r.string()  # style string
    _ = mode_guid
    return voice


# --- images ---


def _read_images(
    r: BinaryReader, loc: Locator, palette: list[Rgb], transparent_index: int
) -> LazyImageStore:
    r.seek(loc.offset)
    count = r.u32()
    offsets = []
    for _ in range(count):
        offset = r.u32()
        r.u32()  # size
        r.u32()  # checksum
        offsets.append(offset)
    lut = _palette_lut(palette)
    return LazyImageStore(r.data, offsets, lut, transparent_index)


# --- animations ---


def _read_animations(r: BinaryReader, loc: Locator) -> list[Animation]:
    r.seek(loc.offset)
    count = r.u32()
    entries = []
    for _ in range(count):
        name = r.string()
        offset = r.u32()
        r.u32()  # size
        entries.append((name, offset))
    return [_read_animation(r, off, name) for name, off in entries]


def _read_animation(r: BinaryReader, offset: int, index_name: str) -> Animation:
    r.seek(offset)
    block_name = r.string()
    return_type = r.u8()
    return_name = r.string()
    frame_count = r.u16()
    frames = [_read_frame(r) for _ in range(frame_count)]

    animation = Animation(
        name=index_name or block_name,
        transition_type=return_type,
        frames=frames,
    )
    if return_type not in (1, 2) and return_name:
        animation.return_animation = return_name
    return animation


def _read_frame(r: BinaryReader) -> Frame:
    image_count = r.u16()
    images = []
    for _ in range(image_count):
        image_index = r.u32()
        x = r.i16()
        y = r.i16()
        images.append(FrameImage(image_index, x, y))

    sound_ndx = r.i16()
    duration = r.u16()
    exit_frame = r.i16()

    branches = []
    for _ in range(r.u8()):
        packed = r.u32()
        probability = min(100, (packed >> 16) & 0xFFFF)
        branches.append(FrameBranch(packed & 0xFFFF, probability))

    overlays = []
    for _ in range(r.u8()):
        otype = r.u8()
        replace_flag = r.u8() != 0
        image_index = r.u16()
        r.u8()  # unknown
        rgn_flag = r.u8()
        ox = r.i16()
        oy = r.i16()
        sx = r.i16()
        sy = r.i16()
        overlays.append(
            MouthOverlay(otype, replace_flag, image_index, ox, oy, rgn_flag, sx, sy)
        )

    return Frame(
        images=images,
        duration_ms=duration * 10,  # .acs stores 1/100 s
        branches=branches,
        exit_frame=exit_frame if exit_frame >= 0 else None,
        sound_index=sound_ndx if sound_ndx >= 0 else None,
        mouth_overlays=overlays,
    )


# --- sounds ---


def _read_sounds(r: BinaryReader, loc: Locator) -> list[bytes]:
    if not loc.size:
        return []
    r.seek(loc.offset)
    count = r.u32()
    refs = []
    for _ in range(count):
        offset = r.u32()
        size = r.u32()
        r.u32()  # checksum
        refs.append((offset, size))
    out = []
    for offset, size in refs:
        r.seek(offset)
        out.append(r.take(size))
    return out
