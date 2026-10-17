"""Compact mask deltas for the radio link (Phase 26, little-endian).

``b"SMD1"`` | ``uint32 epoch`` | ``uint16 count`` | ``count x (uint16 index, uint8 allowed)``;
indices refer to ``sorted(prev.keys() | new.keys())``. A key missing from ``new`` encodes as 0.
"""

from __future__ import annotations

import struct
from typing import Mapping

MAGIC = b"SMD1"
_HEADER = struct.Struct("<4sIH")
_ENTRY = struct.Struct("<HB")


def encode_mask_delta(prev: Mapping[str, bool], new: Mapping[str, bool], *, epoch: int) -> bytes:
    keys = sorted(set(prev) | set(new))
    changes = [
        (i, int(bool(new.get(key, False))))
        for i, key in enumerate(keys)
        if bool(prev.get(key, False)) != bool(new.get(key, False))
    ]
    payload = _HEADER.pack(MAGIC, epoch, len(changes))
    return payload + b"".join(_ENTRY.pack(i, allowed) for i, allowed in changes)


def decode_mask_delta(prev: Mapping[str, bool], payload: bytes) -> dict[str, bool]:
    if len(payload) < _HEADER.size:
        raise ValueError("mask delta shorter than its header")
    magic, _epoch, count = _HEADER.unpack_from(payload)
    if magic != MAGIC:
        raise ValueError("not a mask delta (bad magic)")
    if len(payload) != _HEADER.size + count * _ENTRY.size:
        raise ValueError("mask delta has the wrong length")
    keys = sorted(prev)
    out = dict(prev)
    for n in range(count):
        index, allowed = _ENTRY.unpack_from(payload, _HEADER.size + n * _ENTRY.size)
        if index >= len(keys):
            raise ValueError("mask delta index out of range")
        out[keys[index]] = bool(allowed)
    return out
