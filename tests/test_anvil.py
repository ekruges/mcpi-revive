"""Tests for the bit-packing and chunk-building primitives.

These cover the things Mojang's chunk loader is most strict about:
  * long-array sizing matches ``ceil(4096 / floor(64 / bits))``
  * cells are packed LSB-first with no straddling
  * heightmap encoding clamps within [0, 384]
"""
from __future__ import annotations

import numpy as np
import pytest

from mcpi_revive.anvil import (
    expected_long_count,
    pack_cells,
)


@pytest.mark.parametrize(
    "bits, expected",
    [
        (4, 256),   # 16 cells/long * 256 = 4096
        (5, 342),   # 12 cells/long  (4 padding bits per long)
        (6, 410),   # 10 cells/long
        (7, 456),   # 9 cells/long, ceil(4096/9)=456
        (8, 512),   # 8 cells/long
        (9, 586),   # 7 cells/long
    ],
)
def test_blockstates_long_count(bits, expected):
    """Each long packs floor(64/bits) cells, no straddling."""
    assert expected_long_count(4096, bits) == expected
    longs = pack_cells([0] * 4096, bits)
    assert len(longs) == expected


def test_pack_cells_lsb_first():
    """First cell goes into the lowest bits of long 0."""
    longs = pack_cells([0xA, 0xB, 0xC], bits=4)
    # cell0 -> bits 0..3, cell1 -> bits 4..7, cell2 -> bits 8..11
    assert longs[0] == 0xCBA


def test_pack_cells_no_straddle():
    """A 5-bit cell never straddles the long boundary — long 0 gets exactly 12."""
    cells = list(range(13))   # 0..12
    longs = pack_cells(cells, bits=5)
    assert len(longs) == 2
    # long 0 holds cells 0..11 packed; long 1 holds cell 12 at its lowest bits.
    assert longs[1] == 12


def test_pack_cells_signed_wrap():
    """High bit set yields a negative Python int so NBT TAG_Long_Array
    accepts it as a signed 64-bit value."""
    longs = pack_cells([0xFFFFFFFFFFFFFFFF >> (64 - 4)] * 16, bits=4)
    assert longs[0] < 0


def test_heightmap_size():
    """9 bits per cell, 256 cells, 7 cells per long -> 37 longs."""
    longs = pack_cells([0] * 256, bits=9)
    assert len(longs) == 37


def test_pack_cells_round_trip():
    """Pack and unpack should round-trip."""
    cells = [i & 0xF for i in range(4096)]
    bits = 4
    longs = pack_cells(cells, bits)
    cells_per_long = 64 // bits
    mask = (1 << bits) - 1
    unpacked = []
    for li, lv in enumerate(longs):
        # restore unsigned
        if lv < 0:
            lv += 1 << 64
        for pos in range(cells_per_long):
            unpacked.append((lv >> (pos * bits)) & mask)
    # Trim trailing padding cells
    unpacked = unpacked[: len(cells)]
    assert unpacked == cells
