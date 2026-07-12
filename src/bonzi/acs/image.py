"""Convert 8-bit palette indices into top-down straight-alpha RGBA."""

from __future__ import annotations

import numpy as np

from .model import Image, Rgb


def row_stride(width: int) -> int:
    """Row stride in bytes for an 8-bit indexed image, padded to 4 bytes."""
    return (width + 3) & ~3


def indexed_byte_size(width: int, height: int) -> int:
    return row_stride(width) * height


def _palette_lut(palette: list[Rgb]) -> np.ndarray:
    """A 256x3 uint8 RGB lookup table, zero-padded past the palette length."""
    lut = np.zeros((256, 3), dtype=np.uint8)
    n = min(256, len(palette))
    if n:
        lut[:n] = np.asarray(palette[:n], dtype=np.uint8)
    return lut


def indices_to_image(
    indices: bytes,
    width: int,
    height: int,
    palette: list[Rgb] | np.ndarray,
    transparent_index: int,
) -> Image:
    """.acs rows are stored bottom-up (DIB); emit top-down RGBA, keying alpha."""
    lut = palette if isinstance(palette, np.ndarray) else _palette_lut(palette)
    stride = row_stride(width)
    idx = np.frombuffer(indices, dtype=np.uint8, count=stride * height)
    idx = idx.reshape(height, stride)[:, :width]
    idx = idx[::-1]  # bottom-up -> top-down

    rgba = np.empty((height, width, 4), dtype=np.uint8)
    rgba[..., :3] = lut[idx]
    rgba[..., 3] = np.where(idx == transparent_index, 0, 255).astype(np.uint8)
    return Image(width=width, height=height, rgba=rgba.tobytes())
