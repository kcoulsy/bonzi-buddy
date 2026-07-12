"""Little-endian, cursor-based binary reader for the Microsoft Agent .acs format.

The .acs container is entirely little-endian. Strings are length-prefixed
UTF-16LE. See ``parser.py`` for how the pieces fit together.
"""

from __future__ import annotations

import struct


class BinaryReader:
    """A seekable cursor over a bytes buffer with typed little-endian reads."""

    __slots__ = ("data", "pos")

    def __init__(self, data: bytes, start: int = 0) -> None:
        self.data = data
        self.pos = start

    @property
    def length(self) -> int:
        return len(self.data)

    def seek(self, p: int) -> None:
        self.pos = p

    def skip(self, n: int) -> None:
        self.pos += n

    def u8(self) -> int:
        v = self.data[self.pos]
        self.pos += 1
        return v

    def u16(self) -> int:
        v = struct.unpack_from("<H", self.data, self.pos)[0]
        self.pos += 2
        return v

    def i16(self) -> int:
        v = struct.unpack_from("<h", self.data, self.pos)[0]
        self.pos += 2
        return v

    def u32(self) -> int:
        v = struct.unpack_from("<I", self.data, self.pos)[0]
        self.pos += 4
        return v

    def i32(self) -> int:
        v = struct.unpack_from("<i", self.data, self.pos)[0]
        self.pos += 4
        return v

    def take(self, n: int) -> bytes:
        out = self.data[self.pos : self.pos + n]
        self.pos += n
        return out

    def guid(self) -> str:
        """A 16-byte GUID formatted ``{XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX}``."""
        d1 = self.u32()
        d2 = self.u16()
        d3 = self.u16()
        rest = [self.u8() for _ in range(8)]
        tail = "".join(f"{b:02X}" for b in rest)
        return f"{{{d1:08X}-{d2:04X}-{d3:04X}-{tail[:4]}-{tail[4:]}}}"

    def string(self, null_terminated: bool = True) -> str:
        """Length-prefixed UTF-16LE string: ``u32 charLen`` + ``charLen`` code units.

        A non-empty string is followed by a NUL code unit when ``null_terminated``.
        """
        char_len = self.u32()
        if char_len == 0:
            return ""
        raw = self.data[self.pos : self.pos + char_len * 2]
        self.pos += char_len * 2
        if null_terminated:
            self.pos += 2
        return raw.decode("utf-16-le")
