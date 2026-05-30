"""MCPI world dir -> Java save dir."""
from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np
from nbt import nbt

from .anvil import (
    DATA_VERSION_DEFAULT,
    build_chunk_nbt,
    build_section,
    write_empty_region,
    write_region,
)
from .blocks import mcpi_to_java_state
from .parser import (
    INTERNAL_HEIGHT,
    WORLD_CHUNKS_X,
    WORLD_CHUNKS_Z,
    parse_blocks_and_data,
    parse_level_dat,
)
from .worldgen import install_void_worldgen

log = logging.getLogger(__name__)

MIN_SECTION_Y = -4
MAX_SECTION_Y = 19
MIN_WORLD_Y = MIN_SECTION_Y * 16  # -64

# MCPI block IDs that need an update tick on load so they fall / flow
# instead of hanging as "ghost" blocks until poked.
PHYSICS_IDS = frozenset({
    8, 9,    # water flowing + still
    10, 11,  # lava
    12,      # sand
    13,      # gravel
    78,      # snow layer
})

# Shift the MCPI world down so MCPI y=0 lands at modern y=Y_SHIFT.
# -64 puts MCPI bedrock at modern bedrock level (the world's floor).
Y_SHIFT = -64


def _decode_states(blocks: np.ndarray, data: np.ndarray) -> np.ndarray:
    """Return a (X, Y, Z) object array of (name, properties) tuples.

    Each unique (id, data) pair is decoded once and cached.
    """
    cache: Dict[Tuple[int, int], Tuple[str, Dict[str, str]]] = {}
    flat_blocks = blocks.reshape(-1)
    flat_data = data.reshape(-1)
    out = np.empty(flat_blocks.shape, dtype=object)
    for i, (b, d) in enumerate(zip(flat_blocks, flat_data)):
        # Air shortcut — far and away the most common
        if b == 0:
            out[i] = ("air", {})
            continue
        key = (int(b), int(d))
        st = cache.get(key)
        if st is None:
            st = mcpi_to_java_state(b, d)
            cache[key] = st
        out[i] = st
    return out.reshape(blocks.shape)


_DOOR_NAMES = frozenset({"oak_door", "iron_door"})

# Blocks whose connection state must be set explicitly in modern Java.
_FENCE_NAMES = frozenset({"oak_fence", "nether_brick_fence"})
_PANE_NAMES = frozenset({"glass_pane", "iron_bars"})

# Things fences/panes definitely don't connect to. Everything else is
# treated as solid (over-connection is a less ugly failure mode than
# under-connection).
_NEVER_CONNECT = frozenset({
    "air",
    "water", "lava",
    "torch", "wall_torch", "redstone_torch", "redstone_wall_torch",
    "dandelion", "poppy", "brown_mushroom", "red_mushroom",
    "oak_sapling", "spruce_sapling", "birch_sapling", "jungle_sapling",
    "grass", "dead_bush", "lily_pad",
    "wheat", "sugar_cane", "cactus",
    "snow",
    "redstone_wire",
    "ladder",
    "rail", "powered_rail", "detector_rail",
    "fire",
    "oak_door", "iron_door",
    "red_bed",
    "oak_trapdoor",
    "stonecutter",
    "fire",
    "magenta_wool",  # our "unknown" placeholder — be safe
})


def _stitch_doors(states: np.ndarray) -> None:
    """MCPI splits door state across two halves (facing+open on the lower,
    hinge on the upper). Modern Java MC requires both halves to share every
    property — un-stitched doors render with mismatched halves ("broken door").

    Walks every (x, z) column and merges adjacent door halves in place.
    """
    sx, sy, sz = states.shape
    for x in range(sx):
        for z in range(sz):
            for y in range(sy - 1):
                lower = states[x, y, z]
                upper = states[x, y + 1, z]
                if not isinstance(lower, tuple) or not isinstance(upper, tuple):
                    continue
                lname, lprops = lower
                uname, uprops = upper
                if lname not in _DOOR_NAMES or uname not in _DOOR_NAMES or lname != uname:
                    continue
                if lprops.get("half") != "lower" or uprops.get("half") != "upper":
                    continue
                facing = lprops.get("facing", "north")
                is_open = lprops.get("open", "false")
                hinge = uprops.get("hinge", "left")
                states[x, y, z] = (lname, {
                    "half": "lower", "facing": facing, "open": is_open,
                    "hinge": hinge, "powered": "false",
                })
                states[x, y + 1, z] = (uname, {
                    "half": "upper", "facing": facing, "open": is_open,
                    "hinge": hinge, "powered": "false",
                })


def _stitch_beds(states: np.ndarray, blocks: np.ndarray) -> None:
    """Pair up bed halves and derive `facing` from their actual relative
    positions instead of trusting MCPI's data nibble.

    Modern Java beds need both halves to share `facing` (the direction from
    foot to head), and the matching head/foot must be in the adjacent block
    in that direction. MCPI's per-half facing nibbles don't always match
    modern Java's convention, which makes beds render as ghost halves.

    Orphan halves (no matching partner within 1 block) get replaced with
    air rather than left as ghost blocks.
    """
    bed_positions = np.argwhere(blocks == 26)
    bed_set = {tuple(p.tolist()) for p in bed_positions}
    if not bed_set:
        return

    dirs = (
        ("north", 0, 0, -1),
        ("south", 0, 0, 1),
        ("west", -1, 0, 0),
        ("east", 1, 0, 0),
    )

    processed: set = set()
    for pos_arr in bed_positions:
        pos = tuple(pos_arr.tolist())
        if pos in processed:
            continue
        state = states[pos]
        if not isinstance(state, tuple) or state[0] != "red_bed":
            continue
        part = state[1].get("part", "foot")

        partner = None
        for _, dx, dy, dz in dirs:
            n = (pos[0] + dx, pos[1] + dy, pos[2] + dz)
            if n in bed_set and n not in processed:
                ns = states[n]
                if isinstance(ns, tuple) and ns[0] == "red_bed":
                    if ns[1].get("part", "foot") != part:
                        partner = n
                        break

        if partner is None:
            # Orphan bed half — remove rather than leave as a ghost.
            states[pos] = ("air", {})
            processed.add(pos)
            continue

        foot, head = (pos, partner) if part == "foot" else (partner, pos)
        ddx, ddz = head[0] - foot[0], head[2] - foot[2]
        if ddx == 1:
            facing = "east"
        elif ddx == -1:
            facing = "west"
        elif ddz == 1:
            facing = "south"
        elif ddz == -1:
            facing = "north"
        else:
            facing = "north"  # foot and head somehow at same column

        common = {"facing": facing, "occupied": "false"}
        states[foot] = ("red_bed", {"part": "foot", **common})
        states[head] = ("red_bed", {"part": "head", **common})
        processed.add(pos)
        processed.add(partner)


def _stitch_connections(states: np.ndarray, blocks: np.ndarray) -> None:
    """Set north/south/east/west on fences, glass panes, iron bars.

    Modern Java stores these as block state and won't recompute them at
    render time — without this pass, every fence and glass pane renders
    as an unconnected post.

    Uses raw MCPI block ids to locate targets fast, then operates on the
    decoded state array.
    """
    fence_mask = np.isin(blocks, [85, 113])
    pane_mask = np.isin(blocks, [101, 102])
    targets = np.argwhere(fence_mask | pane_mask)
    sx, sy, sz = states.shape

    def name_at(x: int, y: int, z: int) -> str:
        if 0 <= x < sx and 0 <= y < sy and 0 <= z < sz:
            s = states[x, y, z]
            if isinstance(s, tuple):
                return s[0]
        return "air"

    dirs = [(-1, 0, "west"), (1, 0, "east"), (0, -1, "north"), (0, 1, "south")]

    for x, y, z in targets:
        state = states[x, y, z]
        if not isinstance(state, tuple):
            continue
        name, props = state
        new_props = dict(props)
        for dx, dz, dname in dirs:
            n = name_at(x + dx, y, z + dz)
            new_props[dname] = "false" if n in _NEVER_CONNECT else "true"
        new_props.setdefault("waterlogged", "false")
        states[x, y, z] = (name, new_props)


def _compute_highest_solid(blocks: np.ndarray) -> np.ndarray:
    nonair = blocks != 0
    flipped = nonair[:, ::-1, :]
    any_y = flipped.any(axis=1)
    first_top = flipped.argmax(axis=1)
    top_mcpi_y = (INTERNAL_HEIGHT - 1) - first_top
    top_world_y = top_mcpi_y + Y_SHIFT
    return np.where(any_y, top_world_y, MIN_WORLD_Y - 1)


def _scaffold_from_template(template: Path, dest: Path) -> None:
    shutil.copytree(template, dest)
    for sub in ("dimensions", "region"):
        d = dest / sub
        if d.exists():
            for mca in d.rglob("*.mca"):
                mca.unlink()
    (dest / "session.lock").unlink(missing_ok=True)
    pdata = dest / "players" / "data"
    if pdata.exists():
        for f in pdata.iterdir():
            if f.is_file():
                f.unlink()


def _patch_level_dat(path: Path, level_name: str, spawn: Tuple[int, int, int]) -> None:
    f = nbt.NBTFile(str(path))
    data = f["Data"]
    names = {t.name for t in data.tags}

    def set_tag(name, cls, value):
        if name in names:
            data[name].value = value
        else:
            t = cls(value=value); t.name = name; data.tags.append(t); names.add(name)

    set_tag("LevelName", nbt.TAG_String, level_name)
    set_tag("GameType", nbt.TAG_Int, 1)
    set_tag("allowCommands", nbt.TAG_Byte, 1)
    set_tag("initialized", nbt.TAG_Byte, 1)

    if "spawn" in names:
        sp = data["spawn"]
        pos = nbt.TAG_Int_Array(name="pos"); pos.value = list(spawn)
        sp.tags = [t for t in sp.tags if t.name != "pos"] + [pos]
    else:
        set_tag("SpawnX", nbt.TAG_Int, spawn[0])
        set_tag("SpawnY", nbt.TAG_Int, spawn[1])
        set_tag("SpawnZ", nbt.TAG_Int, spawn[2])
    f.write_file(str(path))


def convert(
    mcpi_world_dir: os.PathLike,
    out_dir: os.PathLike,
    *,
    level_name: Optional[str] = None,
    template_world: Optional[os.PathLike] = None,
    spawn: Optional[Tuple[int, int, int]] = None,
    data_version: int = DATA_VERSION_DEFAULT,
    void_surroundings: bool = True,
) -> Path:
    if template_world is None:
        raise ValueError("template_world is required — pass a fresh Java save dir")

    mcpi_world_dir = Path(mcpi_world_dir)
    out_dir = Path(out_dir)

    log.info("reading MCPI level.dat")
    mcpi_meta = parse_level_dat(mcpi_world_dir)
    if level_name is None:
        level_name = mcpi_meta.get("LevelName") or mcpi_world_dir.name
    if spawn is None:
        mcpi_spawn = mcpi_meta.get("Spawn")
        if mcpi_spawn:
            sx, sy, sz = mcpi_spawn
            spawn = (sx, sy + Y_SHIFT + 2, sz)
        else:
            spawn = (128, MIN_WORLD_Y + 70, 128)

    log.info("cloning template")
    if out_dir.exists():
        shutil.rmtree(out_dir)
    _scaffold_from_template(Path(template_world), out_dir)

    log.info("parsing chunks.dat")
    blocks, metadata = parse_blocks_and_data(mcpi_world_dir)

    log.info("decoding block states")
    states = _decode_states(blocks, metadata)
    _stitch_doors(states)
    _stitch_beds(states, blocks)
    _stitch_connections(states, blocks)
    highest = _compute_highest_solid(blocks)

    # Per (cx, cz, section_idx) list of encoded local positions
    # that need on-load update. Built from raw MCPI block ids.
    physics_mask = np.isin(blocks, list(PHYSICS_IDS))

    log.info("building chunks")
    chunks: Dict[Tuple[int, int], nbt.NBTFile] = {}
    air_state = ("air", {})
    empty_section = np.empty((16, 16, 16), dtype=object)
    empty_section[:] = [[[air_state] * 16] * 16] * 16
    for cx in range(WORLD_CHUNKS_X):
        for cz in range(WORLD_CHUNKS_Z):
            sections = []
            post_processing: list[list[int]] = []
            for sy in range(MIN_SECTION_Y, MAX_SECTION_Y + 1):
                world_y_base = sy * 16
                mcpi_y_base = world_y_base - Y_SHIFT
                if 0 <= mcpi_y_base and mcpi_y_base + 16 <= INTERNAL_HEIGHT:
                    block_slice = states[
                        cx * 16 : (cx + 1) * 16,
                        mcpi_y_base : mcpi_y_base + 16,
                        cz * 16 : (cz + 1) * 16,
                    ]
                    phys_slice = physics_mask[
                        cx * 16 : (cx + 1) * 16,
                        mcpi_y_base : mcpi_y_base + 16,
                        cz * 16 : (cz + 1) * 16,
                    ]
                    # Find positions of physics blocks. Encode as Short:
                    # (z << 8) | (y << 4) | x for the local block position.
                    xs, ys, zs = np.where(phys_slice)
                    post_processing.append([
                        int((int(z) << 8) | (int(y) << 4) | int(x))
                        for x, y, z in zip(xs, ys, zs)
                    ])
                else:
                    block_slice = empty_section
                    post_processing.append([])
                sections.append(build_section(sy, block_slice))

            chunks[(cx, cz)] = build_chunk_nbt(
                cx, cz,
                sections=sections,
                min_section_y=MIN_SECTION_Y,
                highest_solid_y=highest[cx * 16 : (cx + 1) * 16, cz * 16 : (cz + 1) * 16],
                min_world_y=MIN_WORLD_Y,
                data_version=data_version,
                post_processing=post_processing,
            )

    log.info("writing region")
    region_root = out_dir / "dimensions" / "minecraft" / "overworld"
    write_region(region_root / "region" / "r.0.0.mca", chunks)
    write_empty_region(region_root / "entities" / "r.0.0.mca")
    write_empty_region(region_root / "poi" / "r.0.0.mca")

    log.info("patching level.dat: name=%r spawn=%r", level_name, spawn)
    _patch_level_dat(out_dir / "level.dat", level_name, spawn)

    if void_surroundings:
        log.info("installing void world generator")
        seed = mcpi_meta.get("RandomSeed") or 0
        install_void_worldgen(out_dir, seed=int(seed), data_version=data_version)

    (out_dir / "session.lock").write_bytes(b"\xe2\x98\x83")

    log.info("done: %s", out_dir)
    return out_dir
