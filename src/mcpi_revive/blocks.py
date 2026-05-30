"""MCPI (id, data) -> modern Java block name + state properties.

MCPI inherits Minecraft Beta 1.8 data values. Each block ID may use the 4-bit
data nibble for subtype, facing, axis, half, etc.
"""
from __future__ import annotations

from typing import Dict, Tuple

# (id, data) -> (name, properties). Properties values are NBT strings.
# A small "decoder" registry: id -> function(data) -> (name, properties).

State = Tuple[str, Dict[str, str]]

WOOL_COLORS = (
    "white", "orange", "magenta", "light_blue",
    "yellow", "lime", "pink", "gray",
    "light_gray", "cyan", "purple", "blue",
    "brown", "green", "red", "black",
)
WOOD_VARIANTS = ("oak", "spruce", "birch", "jungle")
STAIR_FACING = {0: "east", 1: "west", 2: "south", 3: "north"}
TORCH_WALL = {1: "east", 2: "west", 3: "south", 4: "north"}
DOOR_FACING_LOWER = {0: "east", 1: "south", 2: "west", 3: "north"}
TRAPDOOR_FACING = {0: "south", 1: "north", 2: "east", 3: "west"}
HORIZONTAL_FACING = {2: "north", 3: "south", 4: "west", 5: "east"}
SLAB_VARIANTS = (
    "smooth_stone", "sandstone", "oak", "cobblestone",
    "brick", "stone_brick", "nether_brick", "quartz",
)
QUARTZ_AXIS = {2: "y", 3: "x", 4: "z"}


def _wool(d: int) -> State:
    return (f"{WOOL_COLORS[d & 0x0F]}_wool", {})


def _log(d: int) -> State:
    variant = WOOD_VARIANTS[(d & 0x03) % len(WOOD_VARIANTS)]
    axis = ("y", "x", "z", "none")[(d >> 2) & 0x03]
    return (f"{variant}_log", {"axis": axis} if axis != "none" else {})


def _leaves(d: int) -> State:
    variant = WOOD_VARIANTS[(d & 0x03) % len(WOOD_VARIANTS)]
    props: Dict[str, str] = {"persistent": "true", "distance": "7"}
    return (f"{variant}_leaves", props)


def _sapling(d: int) -> State:
    variant = WOOD_VARIANTS[(d & 0x03) % len(WOOD_VARIANTS)]
    return (f"{variant}_sapling", {})


def _slab(d: int) -> State:
    variant = SLAB_VARIANTS[d & 0x07]
    half = "top" if (d & 0x08) else "bottom"
    return (f"{variant}_slab", {"type": half})


def _double_slab(d: int) -> State:
    variant = SLAB_VARIANTS[d & 0x07]
    return (f"{variant}_slab", {"type": "double"})


def _stairs(name: str):
    def decode(d: int) -> State:
        facing = STAIR_FACING.get(d & 0x03, "north")
        half = "top" if (d & 0x04) else "bottom"
        return (name, {"facing": facing, "half": half})
    return decode


def _torch(d: int) -> State:
    if d == 5 or d == 0:
        return ("torch", {})
    facing = TORCH_WALL.get(d & 0x07, "north")
    return ("wall_torch", {"facing": facing})


def _door(name: str):
    def decode(d: int) -> State:
        if d & 0x08:  # upper half
            hinge = "right" if (d & 0x01) else "left"
            return (name, {"half": "upper", "hinge": hinge, "facing": "north", "open": "false"})
        facing = DOOR_FACING_LOWER.get(d & 0x03, "north")
        is_open = "true" if (d & 0x04) else "false"
        return (name, {"half": "lower", "facing": facing, "open": is_open, "hinge": "left"})
    return decode


def _ladder(d: int) -> State:
    return ("ladder", {"facing": HORIZONTAL_FACING.get(d & 0x07, "north")})


def _trapdoor(d: int) -> State:
    facing = TRAPDOOR_FACING.get(d & 0x03, "north")
    is_open = "true" if (d & 0x04) else "false"
    half = "top" if (d & 0x08) else "bottom"
    return ("oak_trapdoor", {"facing": facing, "open": is_open, "half": half})


def _chest(d: int) -> State:
    return ("chest", {"facing": HORIZONTAL_FACING.get(d & 0x07, "north"), "type": "single"})


def _furnace(lit: bool):
    def decode(d: int) -> State:
        return ("furnace", {"facing": HORIZONTAL_FACING.get(d & 0x07, "north"), "lit": str(lit).lower()})
    return decode


def _bed(d: int) -> State:
    facing = {0: "south", 1: "west", 2: "north", 3: "east"}.get(d & 0x03, "north")
    part = "head" if (d & 0x08) else "foot"
    occupied = "true" if (d & 0x04) else "false"
    return ("red_bed", {"facing": facing, "part": part, "occupied": occupied})


def _quartz(d: int) -> State:
    if d == 0:
        return ("quartz_block", {})
    if d == 1:
        return ("chiseled_quartz_block", {})
    if d in QUARTZ_AXIS:
        return ("quartz_pillar", {"axis": QUARTZ_AXIS[d]})
    return ("quartz_block", {})


def _water(d: int) -> State:
    return ("water", {"level": str(d & 0x0F)})


def _lava(d: int) -> State:
    return ("lava", {"level": str(d & 0x0F)})


# Plain blocks (no data-dependent state)
PLAIN: Dict[int, str] = {
    0:   "air",
    1:   "stone",
    2:   "grass_block",
    3:   "dirt",
    4:   "cobblestone",
    5:   "oak_planks",
    7:   "bedrock",
    12:  "sand",
    13:  "gravel",
    14:  "gold_ore",
    15:  "iron_ore",
    16:  "coal_ore",
    20:  "glass",
    21:  "lapis_ore",
    22:  "lapis_block",
    24:  "sandstone",
    41:  "gold_block",
    42:  "iron_block",
    45:  "bricks",
    46:  "tnt",
    47:  "bookshelf",
    48:  "mossy_cobblestone",
    49:  "obsidian",
    56:  "diamond_ore",
    57:  "diamond_block",
    58:  "crafting_table",
    60:  "farmland",
    73:  "redstone_ore",
    81:  "cactus",
    82:  "clay",
    85:  "oak_fence",
    95:  "barrier",                # PE invisible bedrock
    98:  "stone_bricks",
    102: "glass_pane",
    245: "stonecutter",            # MCPI legacy stonecutter
    246: "magma_block",            # glowing obsidian
    247: "obsidian",               # nether reactor core
}

# Data-aware decoders
DECODERS = {
    6:   _sapling,
    8:   _water,
    9:   _water,
    10:  _lava,
    11:  _lava,
    17:  _log,
    18:  _leaves,
    26:  _bed,
    35:  _wool,
    43:  _double_slab,
    44:  _slab,
    50:  _torch,
    53:  _stairs("oak_stairs"),
    54:  _chest,
    61:  _furnace(False),
    62:  _furnace(True),
    64:  _door("oak_door"),
    65:  _ladder,
    67:  _stairs("cobblestone_stairs"),
    96:  _trapdoor,
    109: _stairs("stone_brick_stairs"),
    155: _quartz,
}

FALLBACK = "magenta_wool"


def mcpi_to_java_state(mcpi_id: int, data: int = 0) -> State:
    """Return (block_name_without_prefix, properties_dict)."""
    mcpi_id = int(mcpi_id)
    if mcpi_id in PLAIN:
        return (PLAIN[mcpi_id], {})
    dec = DECODERS.get(mcpi_id)
    if dec is not None:
        return dec(int(data))
    return (FALLBACK, {})


# Back-compat helper used by the simpler block-only path
def mcpi_to_java_name(mcpi_id: int) -> str:
    name, _ = mcpi_to_java_state(mcpi_id, 0)
    return name
