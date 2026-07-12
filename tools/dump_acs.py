"""Verify the .acs decoder against a real character file.

Prints a structural summary and dumps a few animations to PNG (and a contact
sheet) so the decode can be eyeballed.

    python tools/dump_acs.py assets/Bonzi.acs [--out /tmp/bonzi_dump]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from PIL import Image as PILImage  # noqa: E402

from bonzi.acs import parse_acs  # noqa: E402
from bonzi.acs.model import Character, Image  # noqa: E402


def to_pil(img: Image) -> PILImage.Image:
    if img.width == 0 or img.height == 0:
        return PILImage.new("RGBA", (1, 1))
    return PILImage.frombytes("RGBA", (img.width, img.height), img.rgba)


def compose_frame(char: Character, anim_name: str, frame_idx: int) -> PILImage.Image:
    """Composite a frame's images onto the character-sized canvas."""
    anim = char.animation(anim_name)
    canvas = PILImage.new("RGBA", (char.width, char.height), (0, 0, 0, 0))
    if anim is None or frame_idx >= len(anim.frames):
        return canvas
    for fi in anim.frames[frame_idx].images:
        if fi.image_index >= len(char.images):
            continue
        sprite = to_pil(char.images[fi.image_index])
        canvas.alpha_composite(sprite, (fi.x, fi.y))
    return canvas


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("acs", type=Path)
    ap.add_argument("--out", type=Path, default=Path("/tmp/bonzi_dump"))
    args = ap.parse_args()

    char = parse_acs(args.acs.read_bytes())
    args.out.mkdir(parents=True, exist_ok=True)

    print(f"Character : {char.name!r}  guid={char.guid}")
    print(f"Size      : {char.width} x {char.height}")
    print(f"Palette   : {len(char.palette)} colors  (transparent idx {char.transparent_index})")
    print(f"Images    : {len(char.images)}")
    print(f"Animations: {len(char.animations)}")
    print(f"Sounds    : {len(char.sounds)}")
    print(f"Voice     : speed={char.voice.speed} pitch={char.voice.pitch} lang={char.voice.language_id}")
    print(f"States    : {', '.join(sorted(char.states)) or '(none)'}")

    # size sanity: how many images decoded to non-empty
    nonempty = sum(1 for im in char.images if im.width and im.height)
    print(f"\nNon-empty images: {nonempty}/{len(char.images)}")

    # dump first frame of a handful of named animations, if present
    wanted = ["RestPose", "Greet", "Wave", "Speak", "Idle1_1", "Announce", "Congratulate"]
    present = [a.name for a in char.animations]
    picks = [w for w in wanted if w in present] or present[:6]
    print(f"\nDumping first frame of: {picks}")
    for name in picks:
        img = compose_frame(char, name, 0)
        p = args.out / f"anim_{name}.png"
        img.save(p)
        anim = char.animation(name)
        print(f"  {name:16} frames={len(anim.frames):3}  -> {p}")

    # contact sheet of the first 64 raw sprites
    cols = 8
    thumb = 64
    rows = (min(64, len(char.images)) + cols - 1) // cols
    sheet = PILImage.new("RGBA", (cols * thumb, rows * thumb), (40, 40, 40, 255))
    for i, im in enumerate(char.images[:64]):
        pil = to_pil(im)
        pil.thumbnail((thumb, thumb))
        sheet.alpha_composite(pil, ((i % cols) * thumb, (i // cols) * thumb))
    sheet_path = args.out / "sprites_contact_sheet.png"
    sheet.save(sheet_path)
    print(f"\nContact sheet -> {sheet_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
