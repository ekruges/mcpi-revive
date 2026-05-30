from mcpi_revive.blocks import mcpi_to_java_state as s


def test_air():
    assert s(0) == ("air", {})


def test_bedrock():
    assert s(7) == ("bedrock", {})


def test_wool_colors():
    assert s(35, 0) == ("white_wool", {})
    assert s(35, 14) == ("red_wool", {})
    assert s(35, 15) == ("black_wool", {})


def test_log_axis():
    name, props = s(17, 0)         # oak, Y axis
    assert name == "oak_log"
    assert props.get("axis") == "y"
    name, props = s(17, 4)         # oak, X axis
    assert props.get("axis") == "x"


def test_leaves_persistent():
    name, props = s(18, 0)
    assert name == "oak_leaves"
    assert props.get("persistent") == "true"


def test_slab_variant_and_half():
    name, props = s(44, 0)
    assert name == "smooth_stone_slab"
    assert props.get("type") == "bottom"
    name, props = s(44, 1 | 0x08)  # sandstone, top
    assert name == "sandstone_slab"
    assert props.get("type") == "top"


def test_stairs_facing_and_half():
    name, props = s(53, 0)
    assert name == "oak_stairs"
    assert props["facing"] == "east"
    assert props["half"] == "bottom"
    _, props = s(53, 0x04 | 2)
    assert props["half"] == "top"
    assert props["facing"] == "south"


def test_door_lower_upper():
    name, props = s(64, 0)
    assert name == "oak_door"
    assert props["half"] == "lower"
    _, props = s(64, 0x08)
    assert props["half"] == "upper"


def test_quartz_variants():
    assert s(155, 0)[0] == "quartz_block"
    assert s(155, 1)[0] == "chiseled_quartz_block"
    name, props = s(155, 3)
    assert name == "quartz_pillar"
    assert props["axis"] == "x"


def test_stonecutter():
    assert s(245)[0] == "stonecutter"


def test_water_level():
    name, props = s(9, 7)
    assert name == "water"
    assert props["level"] == "7"


def test_unknown_id_fallback():
    assert s(200) == ("magenta_wool", {})
