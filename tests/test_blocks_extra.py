from mcpi_revive.blocks import mcpi_to_java_state as s


def test_glowstone_ice_clay_misc():
    assert s(79)[0] == "ice"
    assert s(80)[0] == "snow_block"
    assert s(82)[0] == "clay"
    assert s(89)[0] == "glowstone"
    assert s(87)[0] == "netherrack"
    assert s(88)[0] == "soul_sand"


def test_pumpkin_and_jack_o_lantern():
    name, props = s(86, 0)
    assert name == "pumpkin"
    assert props["facing"] == "south"
    name, props = s(91, 2)
    assert name == "jack_o_lantern"
    assert props["facing"] == "north"


def test_wheat_growth():
    name, props = s(59, 0)
    assert name == "wheat"
    assert props["age"] == "0"
    _, props = s(59, 7)
    assert props["age"] == "7"


def test_snow_layer():
    name, props = s(78, 0)
    assert name == "snow"
    assert props["layers"] == "1"
    _, props = s(78, 7)
    assert props["layers"] == "8"


def test_redstone_torch():
    name, props = s(75, 5)
    assert name == "redstone_torch"
    assert props["lit"] == "false"
    name, props = s(76, 5)
    assert props["lit"] == "true"
    name, props = s(76, 1)
    assert name == "redstone_wall_torch"
    assert props["facing"] == "east"


def test_cake_bites():
    _, props = s(92, 3)
    assert props["bites"] == "3"


def test_cactus_age():
    _, props = s(81, 5)
    assert props["age"] == "5"


def test_sugar_cane_age():
    _, props = s(83, 8)
    assert props["age"] == "8"


def test_iron_door():
    name, props = s(71, 0)
    assert name == "iron_door"
    assert props["half"] == "lower"


def test_fence_gate_and_misc_plain():
    assert s(107)[0] == "oak_fence_gate"
    assert s(112)[0] == "nether_bricks"
    assert s(101)[0] == "iron_bars"
    assert s(103)[0] == "melon"
