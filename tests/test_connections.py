import numpy as np
from mcpi_revive.convert import _stitch_connections


def _make(width=3, height=1, depth=3):
    s = np.empty((width, height, depth), dtype=object)
    b = np.zeros((width, height, depth), dtype=np.uint8)
    air = ("air", {})
    for ix in range(width):
        for iy in range(height):
            for iz in range(depth):
                s[ix, iy, iz] = air
    return s, b


def test_two_fences_in_a_row_connect():
    s, b = _make(3, 1, 1)
    s[0, 0, 0] = ("oak_fence", {})
    s[1, 0, 0] = ("oak_fence", {})
    b[0, 0, 0] = 85
    b[1, 0, 0] = 85
    _stitch_connections(s, b)
    # Middle fence... wait we only have 2. Check the left one connects east.
    _, props = s[0, 0, 0]
    assert props["east"] == "true"
    assert props["west"] == "false"
    assert props["north"] == "false"
    assert props["south"] == "false"
    assert props["waterlogged"] == "false"


def test_fence_connects_to_solid_block_not_to_air():
    s, b = _make(3, 1, 1)
    s[0, 0, 0] = ("stone", {})
    s[1, 0, 0] = ("oak_fence", {})
    s[2, 0, 0] = ("air", {})
    b[1, 0, 0] = 85
    _stitch_connections(s, b)
    _, props = s[1, 0, 0]
    assert props["west"] == "true"   # connects to stone
    assert props["east"] == "false"  # air


def test_fence_doesnt_connect_to_torch():
    s, b = _make(3, 1, 1)
    s[0, 0, 0] = ("torch", {})
    s[1, 0, 0] = ("oak_fence", {})
    b[1, 0, 0] = 85
    _stitch_connections(s, b)
    _, props = s[1, 0, 0]
    assert props["west"] == "false"


def test_glass_pane_connects_to_pane():
    s, b = _make(3, 1, 1)
    s[0, 0, 0] = ("glass_pane", {})
    s[1, 0, 0] = ("glass_pane", {})
    b[0, 0, 0] = 102
    b[1, 0, 0] = 102
    _stitch_connections(s, b)
    _, props = s[0, 0, 0]
    assert props["east"] == "true"


def test_non_target_blocks_untouched():
    s, b = _make(3, 1, 3)
    s[1, 0, 1] = ("stone", {})
    _stitch_connections(s, b)
    assert s[1, 0, 1] == ("stone", {})
