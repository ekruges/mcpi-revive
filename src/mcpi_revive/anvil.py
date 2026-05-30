"""Modern (1.18+) Java Anvil chunk + region writer."""
from __future__ import annotations

import io
import math
import struct
import time
import zlib
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np
from nbt import nbt

DATA_VERSION_DEFAULT = 4790  # MC 26.1.2
SECTION_HEIGHT = 16
SECTOR_SIZE = 4096


def pack_cells(cells: Sequence[int], bits: int) -> list[int]:
    """Pack ints into long-array longs, LSB-first, no straddling across longs."""
    if bits <= 0:
        raise ValueError("bits must be positive")
    cells_per_long = 64 // bits
    mask = (1 << bits) - 1
    n_longs = (len(cells) + cells_per_long - 1) // cells_per_long
    longs = [0] * n_longs
    for i, c in enumerate(cells):
        li, pos = divmod(i, cells_per_long)
        longs[li] |= (int(c) & mask) << (pos * bits)
    return [v - (1 << 64) if v >= (1 << 63) else v for v in longs]


def expected_long_count(n_cells: int, bits: int) -> int:
    cells_per_long = 64 // bits
    return (n_cells + cells_per_long - 1) // cells_per_long


def _tag(cls, name, value):
    t = cls(value=value)
    t.name = name
    return t


def build_section(section_y: int, blocks_xyz: np.ndarray) -> nbt.TAG_Compound:
    """Build one section. blocks_xyz is (16,16,16) of Java names (no namespace)."""
    section = nbt.TAG_Compound()
    section.tags.append(_tag(nbt.TAG_Byte, "Y", section_y))

    # YZX flatten
    flat: list[str] = []
    for y in range(SECTION_HEIGHT):
        for z in range(SECTION_HEIGHT):
            for x in range(SECTION_HEIGHT):
                flat.append(blocks_xyz[x, y, z])

    name_to_idx: dict[str, int] = {}
    unique: list[str] = []
    for n in flat:
        if n not in name_to_idx:
            name_to_idx[n] = len(unique)
            unique.append(n)

    block_states = nbt.TAG_Compound(); block_states.name = "block_states"
    palette = nbt.TAG_List(name="palette", type=nbt.TAG_Compound)
    for name in unique:
        entry = nbt.TAG_Compound()
        entry.tags.append(_tag(nbt.TAG_String, "Name", f"minecraft:{name}"))
        palette.tags.append(entry)
    block_states.tags.append(palette)

    if len(unique) > 1:
        bits = max(4, math.ceil(math.log2(len(unique))))
        packed = pack_cells([name_to_idx[n] for n in flat], bits)
        assert len(packed) == expected_long_count(4096, bits)
        data_arr = nbt.TAG_Long_Array(name="data")
        data_arr.value = packed
        block_states.tags.append(data_arr)
    section.tags.append(block_states)

    biomes = nbt.TAG_Compound(); biomes.name = "biomes"
    bp = nbt.TAG_List(name="palette", type=nbt.TAG_String)
    bp.tags.append(nbt.TAG_String(value="minecraft:plains"))
    biomes.tags.append(bp)
    section.tags.append(biomes)

    return section


def _build_heightmaps(highest_solid_y: np.ndarray, min_y: int) -> nbt.TAG_Compound:
    hm = nbt.TAG_Compound(); hm.name = "Heightmaps"
    cells: list[int] = []
    for z in range(16):
        for x in range(16):
            wy = int(highest_solid_y[x, z])
            cells.append(0 if wy < min_y else max(0, min(384, wy - min_y + 1)))
    packed = pack_cells(cells, 9)
    for name in ("MOTION_BLOCKING", "MOTION_BLOCKING_NO_LEAVES", "OCEAN_FLOOR", "WORLD_SURFACE"):
        arr = nbt.TAG_Long_Array(name=name)
        arr.value = list(packed)
        hm.tags.append(arr)
    return hm


def build_chunk_nbt(
    cx: int,
    cz: int,
    *,
    sections: Sequence[nbt.TAG_Compound],
    min_section_y: int,
    highest_solid_y: np.ndarray,
    min_world_y: int,
    data_version: int = DATA_VERSION_DEFAULT,
    status: str = "minecraft:full",
) -> nbt.NBTFile:
    root = nbt.NBTFile()
    root.tags.append(_tag(nbt.TAG_Int, "DataVersion", data_version))
    root.tags.append(_tag(nbt.TAG_Int, "xPos", cx))
    root.tags.append(_tag(nbt.TAG_Int, "yPos", min_section_y))
    root.tags.append(_tag(nbt.TAG_Int, "zPos", cz))
    root.tags.append(_tag(nbt.TAG_String, "Status", status))
    root.tags.append(_tag(nbt.TAG_Long, "LastUpdate", 0))
    root.tags.append(_tag(nbt.TAG_Long, "InhabitedTime", 0))
    root.tags.append(_tag(nbt.TAG_Byte, "isLightOn", 0))
    root.tags.append(_build_heightmaps(highest_solid_y, min_world_y))

    pp = nbt.TAG_List(name="PostProcessing", type=nbt.TAG_List)
    for _ in range(len(sections)):
        pp.tags.append(nbt.TAG_List(type=nbt.TAG_Short))
    root.tags.append(pp)

    secs = nbt.TAG_List(name="sections", type=nbt.TAG_Compound)
    for s in sections:
        secs.tags.append(s)
    root.tags.append(secs)

    root.tags.append(nbt.TAG_List(name="block_entities", type=nbt.TAG_Compound))
    root.tags.append(nbt.TAG_List(name="block_ticks", type=nbt.TAG_Compound))
    root.tags.append(nbt.TAG_List(name="fluid_ticks", type=nbt.TAG_Compound))

    structures = nbt.TAG_Compound(); structures.name = "structures"
    starts = nbt.TAG_Compound(); starts.name = "starts"
    refs = nbt.TAG_Compound(); refs.name = "References"
    structures.tags.append(starts)
    structures.tags.append(refs)
    root.tags.append(structures)

    return root


def write_region(path: Path, chunks: Mapping[tuple[int, int], nbt.NBTFile]) -> None:
    """Write an Anvil region file. Chunks keyed by (cx, cz). zlib compression."""
    path.parent.mkdir(parents=True, exist_ok=True)

    compressed: dict[tuple[int, int], bytes] = {}
    for key, n in chunks.items():
        buf = io.BytesIO()
        n.write_file(buffer=buf)
        compressed[key] = zlib.compress(buf.getvalue(), level=6)

    locations = [0] * 1024
    timestamps = [int(time.time())] * 1024
    sector_data: list[bytes] = []
    current_sector = 2

    for (cx, cz), comp in compressed.items():
        length_field = len(comp) + 1
        chunk_bytes = struct.pack(">IB", length_field, 2) + comp
        sectors = (len(chunk_bytes) + SECTOR_SIZE - 1) // SECTOR_SIZE
        if sectors > 255:
            raise ValueError(f"chunk ({cx},{cz}) needs {sectors} sectors > 255")
        idx = (cz % 32) * 32 + (cx % 32)
        locations[idx] = (current_sector << 8) | sectors
        padded = chunk_bytes + b"\x00" * (sectors * SECTOR_SIZE - len(chunk_bytes))
        sector_data.append(padded)
        current_sector += sectors

    with open(path, "wb") as f:
        for v in locations:
            f.write(struct.pack(">I", v))
        for v in timestamps:
            f.write(struct.pack(">I", v))
        for sd in sector_data:
            f.write(sd)


def write_empty_region(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x00" * (2 * SECTOR_SIZE))
