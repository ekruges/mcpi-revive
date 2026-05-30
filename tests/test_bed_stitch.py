import numpy as np
from mcpi_revive.convert import _stitch_beds


def _make(shape=(3, 1, 3)):
    s = np.empty(shape, dtype=object)
    b = np.zeros(shape, dtype=np.uint8)
    air = ("air", {})
    for ix in range(shape[0]):
        for iy in range(shape[1]):
            for iz in range(shape[2]):
                s[ix, iy, iz] = air
    return s, b


def test_bed_pair_north_south():
    """foot at (1,0,1), head at (1,0,0) -> facing=north on both halves."""
    s, b = _make()
    s[1, 0, 1] = ("red_bed", {"part": "foot", "facing": "south", "occupied": "false"})
    s[1, 0, 0] = ("red_bed", {"part": "head", "facing": "south", "occupied": "false"})
    b[1, 0, 1] = 26
    b[1, 0, 0] = 26
    _stitch_beds(s, b)
    foot_name, foot_props = s[1, 0, 1]
    head_name, head_props = s[1, 0, 0]
    assert foot_name == head_name == "red_bed"
    assert foot_props["part"] == "foot"
    assert head_props["part"] == "head"
    assert foot_props["facing"] == head_props["facing"] == "north"
    assert foot_props["occupied"] == head_props["occupied"] == "false"


def test_bed_pair_east_west():
    """foot at (0,0,1), head at (1,0,1) -> facing=east."""
    s, b = _make()
    s[0, 0, 1] = ("red_bed", {"part": "foot", "facing": "north", "occupied": "false"})
    s[1, 0, 1] = ("red_bed", {"part": "head", "facing": "north", "occupied": "false"})
    b[0, 0, 1] = 26
    b[1, 0, 1] = 26
    _stitch_beds(s, b)
    _, foot_props = s[0, 0, 1]
    _, head_props = s[1, 0, 1]
    assert foot_props["facing"] == head_props["facing"] == "east"


def test_orphan_bed_half_removed():
    s, b = _make()
    s[1, 0, 1] = ("red_bed", {"part": "foot", "facing": "south", "occupied": "false"})
    b[1, 0, 1] = 26
    _stitch_beds(s, b)
    assert s[1, 0, 1] == ("air", {})


def test_no_beds_no_change():
    s, b = _make()
    s[1, 0, 1] = ("stone", {})
    _stitch_beds(s, b)
    assert s[1, 0, 1] == ("stone", {})


def test_two_feet_no_head_both_removed():
    """Two foot halves adjacent without heads — orphan both."""
    s, b = _make((3, 1, 1))
    s[0, 0, 0] = ("red_bed", {"part": "foot", "facing": "south", "occupied": "false"})
    s[1, 0, 0] = ("red_bed", {"part": "foot", "facing": "south", "occupied": "false"})
    b[0, 0, 0] = 26
    b[1, 0, 0] = 26
    _stitch_beds(s, b)
    assert s[0, 0, 0] == ("air", {})
    assert s[1, 0, 0] == ("air", {})
