# Bonzi for Linux

A native **Python + Qt (PySide6)** port of *BonziBUDDY Rewritten* — the purple
Microsoft Agent desktop pet — running directly on Linux. No Wine, no .NET, no
Microsoft Agent runtime: the `.acs` character file is decoded and animated by
this project.

## Status

- ✅ **`.acs` decoder** — full Microsoft Agent v2 format: header, palette, the
  bit-stream LZ77 image codec, all 1246 sprites, 148 animations, 22 sounds,
  voice and state metadata. Lazy-decoded (instant startup).
- ✅ **Desktop pet MVP** — frameless, transparent, always-on-top, draggable
  Bonzi that plays animations, idles, greets, and speaks with a word balloon +
  system TTS. Right-click menu: *Say something*, *Tell a joke*, *Animate ▸*
  (every animation), *Goodbye*.
- ⏳ **Feature parity** — search, sing, calendar/reminders, download manager,
  eBook reader, options, themes (ported from the decompiled original).

## Run

```bash
./run.sh
```

## Voice (optional)

Install any one TTS engine for Bonzi to actually talk (otherwise the balloon
still shows):

```bash
sudo pacman -S espeak-ng        # recommended
# or: festival, or speech-dispatcher (spd-say)
```

## Layout

```
src/bonzi/
  acs/        # the .acs decoder (reader, rle codec, image, parser, lazy store)
  runtime/    # Qt runtime (player, tts, balloon, pet widget)
  app.py      # entry point
tools/dump_acs.py   # decoder verification: dumps sprites/frames to PNG
assets/             # Bonzi.acs + theme images (from the original install)
decompiled/         # ILSpy decompilation of the original app (reference)
reference/          # .acs format reference implementation
```

## Origin & safety

Ported from the abandonware *BonziBUDDY Rewritten* by tmafe.com. A full static
audit of the original binaries (see `decompiled/`) found **no malware** — the
antivirus flags are false positives triggered by the "BonziBuddy" name, the MS
Agent desktop-pet behaviour, and an ancient unsigned installer. No registry
persistence, no C2, no silent downloads.
