import pytest
from mcpi_revive.anvil import expected_long_count, pack_cells


@pytest.mark.parametrize("bits, expected", [
    (4, 256), (5, 342), (6, 410), (7, 456), (8, 512), (9, 586),
])
def test_blockstates_long_count(bits, expected):
    assert expected_long_count(4096, bits) == expected
    assert len(pack_cells([0] * 4096, bits)) == expected


def test_lsb_first():
    longs = pack_cells([0xA, 0xB, 0xC], bits=4)
    assert longs[0] == 0xCBA


def test_no_straddle():
    longs = pack_cells(list(range(13)), bits=5)
    assert len(longs) == 2
    assert longs[1] == 12


def test_signed_wrap():
    longs = pack_cells([0xF] * 16, bits=4)
    assert longs[0] < 0


def test_heightmap_size():
    assert len(pack_cells([0] * 256, bits=9)) == 37


def test_round_trip():
    cells = [i & 0xF for i in range(4096)]
    longs = pack_cells(cells, bits=4)
    out = []
    for lv in longs:
        if lv < 0:
            lv += 1 << 64
        for pos in range(16):
            out.append((lv >> (pos * 4)) & 0xF)
    assert out[: len(cells)] == cells
