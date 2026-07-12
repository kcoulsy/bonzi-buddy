"""Lazy, cached image store.

Decoding all ~1200 sprites up front costs seconds of pure-Python RLE work, but a
running character only ever touches a fraction of them. ``LazyImageStore``
decodes each sprite on first access and caches the result, so startup is
instant and cost is paid per animation actually played.
"""

from __future__ import annotations

import numpy as np

from .image import indexed_byte_size, indices_to_image
from .model import Image
from .reader import BinaryReader
from .rle import decode_image_data


class LazyImageStore:
    __slots__ = ("_data", "_offsets", "_lut", "_transparent", "_cache")

    def __init__(
        self,
        data: bytes,
        offsets: list[int],
        lut: np.ndarray,
        transparent_index: int,
    ) -> None:
        self._data = data
        self._offsets = offsets
        self._lut = lut
        self._transparent = transparent_index
        self._cache: dict[int, Image] = {}

    def __len__(self) -> int:
        return len(self._offsets)

    def __getitem__(self, i: int) -> Image:
        cached = self._cache.get(i)
        if cached is not None:
            return cached
        img = self._decode(self._offsets[i])
        self._cache[i] = img
        return img

    def __iter__(self):
        for i in range(len(self)):
            yield self[i]

    def _decode(self, offset: int) -> Image:
        r = BinaryReader(self._data, offset)
        r.u8()  # unknown1
        width = r.u16()
        height = r.u16()
        compressed = r.u8()
        data_len = r.u32()
        raw = r.take(data_len)

        if width <= 0 or height <= 0:
            return Image(max(0, width), max(0, height), b"")

        decoded_size = indexed_byte_size(width, height)
        if compressed:
            indices: bytes = bytes(decode_image_data(raw, decoded_size))
        elif len(raw) >= decoded_size:
            indices = raw[:decoded_size]
        else:
            indices = raw + bytes(decoded_size - len(raw))
        return indices_to_image(indices, width, height, self._lut, self._transparent)
