"""The .acs image codec: a bit-stream LZ77 over 8-bit palette indices.

This is the algorithm DoubleAgent calls ``DecodeData``. Each compressed image
stream is a header byte (0x00), a 4-byte priming window, a sequence of tokens
read LSB-first from a sliding 32-bit window, and a run of trailing 0xFF bytes.

Tokens are either a literal (flag bit 0, then 8 data bits) or a back-reference
(flag bit 1, then a variable-length distance code, then a gamma-style run
length). Ported to Python from the documented bit-level spec.
"""

from __future__ import annotations


def _u32_at(buf: bytes, p: int) -> int:
    """Little-endian u32 at byte ``p``, zero-padding out-of-range bytes."""
    b0 = buf[p] if 0 <= p < len(buf) else 0
    b1 = buf[p + 1] if 0 <= p + 1 < len(buf) else 0
    b2 = buf[p + 2] if 0 <= p + 2 < len(buf) else 0
    b3 = buf[p + 3] if 0 <= p + 3 < len(buf) else 0
    return b0 | (b1 << 8) | (b2 << 16) | (b3 << 24)


def decode_image_data(src: bytes, target_size: int) -> bytearray:
    """Decode a compressed .acs image stream into ``target_size`` index bytes."""
    out = bytearray(target_size)

    # Preconditions (match DoubleAgent's DecodeData): a leading 0x00 byte and a
    # trailing run of >= 5 0xFF bytes.
    if len(src) <= 7 or src[0] != 0:
        raise ValueError("decode_image_data: missing 0x00 header byte")
    tail = 1
    while src[len(src) - tail] == 0xFF:
        tail += 1
        if tail > 6:
            break
    if tail < 6:
        raise ValueError("decode_image_data: missing 0xFF trailer")

    src_pos = 5  # skip the 5-byte header/priming window
    bit = 0  # bit offset within the current 32-bit window
    out_pos = 0

    while src_pos < len(src) and out_pos < target_size:
        quad = _u32_at(src, src_pos - 4)

        if quad & (1 << (bit & 0xFFFF)):
            # ---- back-reference: decode the copy distance ----
            src_offset = 1
            if quad & (1 << ((bit + 1) & 0xFFFF)):
                if quad & (1 << ((bit + 2) & 0xFFFF)):
                    if quad & (1 << ((bit + 3) & 0xFFFF)):
                        quad = (quad >> ((bit + 4) & 0xFFFF)) & 0x000FFFFF
                        if quad == 0x000FFFFF:
                            break  # end-of-image marker
                        quad += 4673
                        bit += 24
                        src_offset = 2
                    else:
                        quad = (quad >> ((bit + 4) & 0xFFFF)) & 0x00000FFF
                        quad += 577
                        bit += 16
                else:
                    quad = (quad >> ((bit + 3) & 0xFFFF)) & 0x000001FF
                    quad += 65
                    bit += 12
            else:
                quad = (quad >> ((bit + 2) & 0xFFFF)) & 0x0000003F
                quad += 1
                bit += 8
            distance = quad

            src_pos += bit >> 3
            bit &= 7

            # ---- decode the run length (gamma-style code) ----
            run_bits = _u32_at(src, src_pos - 4)
            run_count = 0
            while run_bits & (1 << ((bit + run_count) & 0xFFFF)):
                run_count += 1
                if run_count > 11:
                    break
            run_len = run_bits >> ((bit + run_count + 1) & 0xFFFF)
            run_len &= (1 << run_count) - 1
            run_len += 1 << run_count
            run_len += src_offset
            bit += run_count * 2 + 1

            if out_pos + run_len > target_size:
                break
            if out_pos - distance < 0:
                break
            for _ in range(run_len):
                out[out_pos] = out[out_pos - distance]
                out_pos += 1
        else:
            # ---- literal byte (1 flag bit + 8 data bits) ----
            byte = (quad >> ((bit + 1) & 0xFFFF)) & 0xFF
            bit += 9
            out[out_pos] = byte
            out_pos += 1

        src_pos += bit >> 3
        bit &= 7

    return out
