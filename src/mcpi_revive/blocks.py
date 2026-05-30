"""Mapping from MCPI 1-byte block IDs to modern Java namespaced block names.

MCPI uses a ~92-block subset of Minecraft Beta/Pocket-era block IDs. The IDs
here were collected by inspecting real MCPI saves; a few entries (155, 245)
were observed in user data and mapped to visible placeholder blocks.

The mapping is intentionally simple — only the block name. MCPI's data nibble
(which encodes wool color, slab variant, log rotation, etc.) is currently
discarded, so e.g. all wool comes out white and all stairs face north. Adding
data-nibble support is the obvious next step.
"""
from __future__ import annotations

# Default for any MCPI block id not in MCPI_TO_JAVA. magenta_wool is a deliberate
# eyesore so unmapped blocks are easy to spot in-game.
FALLBACK = "magenta_wool"

MCPI_TO_JAVA: dict[int, str] = {
    0:   "air",
    1:   "stone",
    2:   "grass_block",
    3:   "dirt",
    4:   "cobblestone",
    5:   "oak_planks",
    6:   "oak_sapling",
    7:   "bedrock",
    8:   "water",            # flowing
    9:   "water",            # still
    10:  "lava",             # flowing
    11:  "lava",             # still
    12:  "sand",
    13:  "gravel",
    14:  "gold_ore",
    15:  "iron_ore",
    16:  "coal_ore",
    17:  "oak_log",
    18:  "oak_leaves",
    20:  "glass",
    21:  "lapis_ore",
    22:  "lapis_block",
    24:  "sandstone",
    26:  "red_bed",
    35:  "white_wool",       # MCPI data nibble = color; we lose it
    37:  "dandelion",
    38:  "poppy",
    41:  "gold_block",
    42:  "iron_block",
    43:  "smooth_stone_slab",  # MCPI's "double slab"
    44:  "stone_slab",         # MCPI data nibble = variant; we lose it
    45:  "bricks",
    46:  "tnt",
    47:  "bookshelf",
    48:  "mossy_cobblestone",
    49:  "obsidian",
    50:  "torch",
    53:  "oak_stairs",
    54:  "chest",
    56:  "diamond_ore",
    57:  "diamond_block",
    58:  "crafting_table",
    60:  "farmland",
    61:  "furnace",
    64:  "oak_door",
    65:  "ladder",
    67:  "cobblestone_stairs",
    73:  "redstone_ore",
    81:  "cactus",
    82:  "clay",
    85:  "oak_fence",
    96:  "oak_trapdoor",
    98:  "stone_bricks",
    102: "glass_pane",
    109: "stone_brick_stairs",
    # Observed in user data but unclear in MCPI block list; mapped to
    # visible-but-distinctive placeholders so they show up in-game and
    # the user can re-map later.
    155: "quartz_block",
    245: "purple_wool",
}


def mcpi_to_java_name(mcpi_id: int) -> str:
    """Return the modern Java block name (without ``minecraft:`` prefix)."""
    return MCPI_TO_JAVA.get(int(mcpi_id), FALLBACK)
