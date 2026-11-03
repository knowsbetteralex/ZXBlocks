"""ZX Spectrum TAP writer for a CODE block (no BASIC loader yet)."""

from __future__ import annotations

import struct


def _block(flag: int, payload: bytes) -> bytes:
    block = bytes([flag]) + payload
    checksum = 0
    for value in block:
        checksum ^= value
    return struct.pack("<H", len(block) + 1) + block + bytes([checksum])


def make_code_tap(binary: bytes, name: str, origin: int = 32768) -> bytes:
    """Create a standard header + data TAP pair for LOAD "" CODE."""
    if not binary or len(binary) > 65535 or origin < 0 or origin + len(binary) > 65536:
        raise ValueError("Invalid code size or origin for 64K address space")
    label = name.encode("ascii", errors="strict")[:10].ljust(10, b" ")
    header = bytes([3]) + label + struct.pack("<HHH", len(binary), origin, 32768)
    return _block(0, header) + _block(255, binary)
