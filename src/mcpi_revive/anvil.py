"""Writer for the modern (1.18+) Minecraft Java Anvil chunk and region format.

This is a from-scratch implementation aimed at MC 1.18 — 1.21+ / DataVersion 4790
(MC 26.1.2). The format reference is the current Minecraft Wiki "Chunk format"
and "Region file format" pages, which document the post-1.18 flat layout.

Notable spec points worth re-stating because every legacy library gets them
wrong:

  * Root chunk NBT is **flat** since 1.18 — there's no ``Level`` wrapper.
  * ``sections`` is lowercase; each section has ``Y`` (byte), ``block_states``,
    and ``biomes`` compounds.
  * ``block_states.data`` is a packed long array. The number of longs is
    ``ceil(4096 / floor(64 / bits))`` — Mojang does NOT pack across long
    boundaries. Cell 0 lives in the lowest bits of long 0. Block iteration
    order inside the 16x16x16 section is YZX:
    ``index = y * 256 + z * 16 + x``.
  * Heightmaps store 9 bits per column (heights ``0..384``), 7 cells per long,
    37 longs. Column index ``z * 16 + x``. Value is "blocks above min Y", so
    for a vanilla overworld a block at world y=70 with minY=-64 stores 135.
  * Region file: 4 KiB location table (1024 BE u32, each
    ``(sector << 8) | count``), 4 KiB timestamp table, then chunks at sector
    boundaries. Each chunk starts with a 4-byte BE length prefix that
    *includes* the 1-byte compression scheme but *excludes* itself, followed
    by the compression byte (2 = zlib) and the compressed NBT, padded to a
    multiple of 4096 with zeros.
"""
from __future__ import annotations

import io
import math
import struct
import time
import zlib
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import numpy as np
from nbt import nbt

DATA_VERSION_DEFAULT = 4790   # MC 26.1.2
SECTION_HEIGHT = 16
SECTOR_SIZE = 4096


# --------------------------------------------------------------------------- bit packing

def pack_cells(cells: Sequence[int], bits: int) -> list[int]:
    """Pack a flat sequence of cell values into long-array longs.

    Modern (1.16+) layout: each 64-bit long holds ``floor(64 / bits)`` cells.
    Cells do NOT straddle long boundaries — unused high bits of each long are
    zero. Cell ``k`` lives at bit ``(k % cells_per_long) * bits`` of long
    ``k // cells_per_long``.

    Returns Python ints in two's-complement signed range so they round-trip
    cleanly through NBT's TAG_Long_Array (which is signed-64-bit).
    """
    if bits <= 0:
        raise ValueError("bits must be positive")
    cells_per_long = 64 // bits
    mask = (1 << bits) - 1
    n_longs = (len(cells) + cells_per_long - 1) // cells_per_long
    longs = [0] * n_longs
    for i, c in enumerate(cells):
        li, pos = divmod(i, cells_per_long)
        longs[li] |= (int(c) & mask) << (pos * bits)
    # Convert unsigned -> signed for NBT TAG_Long_Array
    return [v - (1 << 64) if v >= (1 << 63) else v for v in longs]


def expected_long_count(n_cells: int, bits: int) -> int:
    """Number of longs Mojang's PalettedContainer expects for the given size."""
    cells_per_long = 64 // bits
    return (n_cells + cells_per_long - 1) // cells_per_long


# --------------------------------------------------------------------------- NBT building

def _tag(cls, name, value):
    t = cls(value=value)
    t.name = name
    return t


def _build_section(section_y: int, blocks_xyz: np.ndarray) -> nbt.TAG_Compound:
    """Build one section NBT compound.

    ``blocks_xyz`` is a ``(16, 16, 16)`` numpy array of Java block names
    (strings, without the ``minecraft:`` prefix). The caller is responsible
    for mapping from whatever source IDs.
    """
    section = nbt.TAG_Compound()
    section.tags.append(_tag(nbt.TAG_Byte, "Y", section_y))

    # Flatten YZX
    flat: list[str] = []
    for y in range(SECTION_HEIGHT):
        for z in range(SECTION_HEIGHT):
            for x in range(SECTION_HEIGHT):
                flat.append(blocks_xyz[x, y, z])

    # Palette
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
        data_arr = nbt.TAG_Long_Array(name="data")
        data_arr.value = packed
        # Sanity check — Mojang's PalettedContainer rejects mismatched sizes
        assert len(packed) == expected_long_count(4096, bits), (
            f"BlockStates length mismatch: got {len(packed)}, "
            f"expected {expected_long_count(4096, bits)} for {bits} bits"
        )
        block_states.tags.append(data_arr)
    section.tags.append(block_states)

    # Biomes (uniform plains)
    biomes = nbt.TAG_Compound(); biomes.name = "biomes"
    bp = nbt.TAG_List(name="palette", type=nbt.TAG_String)
    bp.tags.append(nbt.TAG_String(value="minecraft:plains"))
    biomes.tags.append(bp)
    section.tags.append(biomes)

    return section


def _build_heightmaps(highest_solid_y: np.ndarray, min_y: int) -> nbt.TAG_Compound:
    """Construct the Heightmaps compound from a 16x16 array of highest-block Y.

    ``highest_solid_y[x, z]`` is the world Y of the highest non-air block in
    that column, or any value < ``min_y`` for fully-air columns. ``min_y`` is
    the chunk's lowest world Y (``-64`` in vanilla).

    Stored value per cell is ``height_world_y - min_y + 1``, clamped to
    ``[0, 384]`` and packed at 9 bits per cell into 37 longs.
    """
    hm = nbt.TAG_Compound(); hm.name = "Heightmaps"
    cells: list[int] = []
    for z in range(16):
        for x in range(16):
            wy = int(highest_solid_y[x, z])
            if wy < min_y:
                cells.append(0)
            else:
                cells.append(max(0, min(384, wy - min_y + 1)))
    packed = pack_cells(cells, 9)
    for name in (
        "MOTION_BLOCKING",
        "MOTION_BLOCKING_NO_LEAVES",
        "OCEAN_FLOOR",
        "WORLD_SURFACE",
    ):
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
    """Assemble a complete chunk NBT in the modern (1.18+) layout."""
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

    # PostProcessing: one empty list per section
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
    structures.tags.append(starts)
    refs = nbt.TAG_Compound(); refs.name = "References"
    structures.tags.append(refs)
    root.tags.append(structures)

    return root


# Convenience wrapper around _build_section for callers who only have raw
# numpy arrays of namespaced block names.
build_section = _build_section


# --------------------------------------------------------------------------- region file

def write_region(path: Path, chunks: Mapping[tuple[int, int], nbt.NBTFile]) -> None:
    """Write a region file containing the given chunks (keyed by ``(cx, cz)``).

    All chunks are zlib-compressed (scheme 2). The region's location table is
    indexed by ``(cz % 32) * 32 + (cx % 32)``.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    compressed: dict[tuple[int, int], bytes] = {}
    for key, nbt_root in chunks.items():
        buf = io.BytesIO()
        nbt_root.write_file(buffer=buf)  # writes raw NBT (no gzip wrapper)
        compressed[key] = zlib.compress(buf.getvalue(), level=6)

    locations = [0] * 1024
    timestamps = [int(time.time())] * 1024
    sector_data: list[bytes] = []
    current_sector = 2  # sectors 0 and 1 are the header

    for (cx, cz), comp in compressed.items():
        length_field = len(comp) + 1  # +1 for compression-scheme byte
        chunk_bytes = struct.pack(">IB", length_field, 2) + comp
        sectors_needed = (len(chunk_bytes) + SECTOR_SIZE - 1) // SECTOR_SIZE
        if sectors_needed > 255:
            raise ValueError(
                f"Chunk ({cx},{cz}) needs {sectors_needed} sectors; "
                "Mojang's 1-byte sector count maxes at 255 (write .mcc external)."
            )
        idx = (cz % 32) * 32 + (cx % 32)
        locations[idx] = (current_sector << 8) | sectors_needed
        padded = chunk_bytes + b"\x00" * (sectors_needed * SECTOR_SIZE - len(chunk_bytes))
        sector_data.append(padded)
        current_sector += sectors_needed

    with open(path, "wb") as f:
        for v in locations:
            f.write(struct.pack(">I", v))
        for v in timestamps:
            f.write(struct.pack(">I", v))
        for sd in sector_data:
            f.write(sd)


def write_empty_region(path: Path) -> None:
    """Write a valid 8 KiB empty region file (no chunks, all-zero header)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x00" * (2 * SECTOR_SIZE))
