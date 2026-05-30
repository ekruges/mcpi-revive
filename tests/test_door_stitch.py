import numpy as np
from mcpi_revive.convert import _stitch_doors


def test_door_halves_share_facing_and_hinge():
    states = np.empty((1, 4, 1), dtype=object)
    states[0, 0, 0] = ("air", {})
    # Lower half: facing=south, open=true
    states[0, 1, 0] = ("oak_door", {
        "half": "lower", "facing": "south", "open": "true",
        "hinge": "left", "powered": "false",
    })
    # Upper half: hinge=right (only useful info MCPI gives us)
    states[0, 2, 0] = ("oak_door", {
        "half": "upper", "facing": "north", "open": "false",
        "hinge": "right", "powered": "false",
    })
    states[0, 3, 0] = ("air", {})

    _stitch_doors(states)

    lower_name, lower_props = states[0, 1, 0]
    upper_name, upper_props = states[0, 2, 0]
    assert lower_name == upper_name == "oak_door"
    assert lower_props["facing"] == upper_props["facing"] == "south"
    assert lower_props["open"] == upper_props["open"] == "true"
    assert lower_props["hinge"] == upper_props["hinge"] == "right"
    assert lower_props["powered"] == upper_props["powered"] == "false"
    assert lower_props["half"] == "lower"
    assert upper_props["half"] == "upper"


def test_stitcher_leaves_non_doors_alone():
    states = np.empty((1, 3, 1), dtype=object)
    states[0, 0, 0] = ("stone", {})
    states[0, 1, 0] = ("stone", {})
    states[0, 2, 0] = ("stone", {})
    _stitch_doors(states)
    assert all(states[0, y, 0] == ("stone", {}) for y in range(3))
