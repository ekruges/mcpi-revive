"""Parser for Minecraft: Pi Edition's chunks.dat format.

The format is documented (loosely) by the pymclevel "PocketWorld" loader and
inferred from inspection of real MCPI saves. A summary:

  * The file is a flat array of 4096-byte sectors. Sector 0 is the location
    table: 1024 big-endian uint32s, each containing
    ``(sector_offset << 8) | sector_count``. Index ``z*32 + x`` in the table
    points to chunk (x, z). Unused entries are zero.
  * Each chunk starts with a 4-byte little-endian length prefix. The remaining
    chunk bytes are uncompressed and consist of, in order:
        blocks       32768 bytes  uint8, indexed as (x*16 + z)*128 + y
        data nibble  16384 bytes  4 bits per cell
        skyLight     16384 bytes  4 bits per cell
        blockLight   16384 bytes  4 bits per cell
        dirtyColumns   256 bytes  per (x, z) column
  * The world is fixed at 16x16 chunks (256 columns wide), 128 tall internally
    even though MCPI gameplay only uses y=0..63. Worlds placed above y=63 are
    preserved in the storage; you can find them in the parsed array.

References:
  https://github.com/mcedit/pymclevel — pocket.py (Python 2)
  Minecraft Pocket Edition 0.6 chunks.dat — reverse-engineered, no official spec
"""
from __future__ import annotations

import struct
from pathlib import Path
from typing import Union

import numpy as np

SECTOR_SIZE = 4096
WORLD_CHUNKS_X = 16
WORLD_CHUNKS_Z = 16
CHUNK_BLOCKS_X = 16
CHUNK_BLOCKS_Z = 16
INTERNAL_HEIGHT = 128

# Public world dimensions
WORLD_WIDTH = WORLD_CHUNKS_X * CHUNK_BLOCKS_X   # 256
WORLD_DEPTH = WORLD_CHUNKS_Z * CHUNK_BLOCKS_Z   # 256
WORLD_HEIGHT = INTERNAL_HEIGHT                   # 128


def parse_chunks_dat(world_dir: Union[str, Path]) -> np.ndarray:
    """Parse an MCPI world directory and return a 3D block-id array.

    The returned array has shape ``(256, 128, 256)`` indexed as ``[x, y, z]``,
    where ``y=0`` is the bottom of the world (bedrock layer for normal worlds).
    Block IDs are MCPI's 1-byte IDs; use :mod:`mcpi_revive.blocks` to translate
    them to modern Java namespaced names.
    """
    world_dir = Path(world_dir)
    data = (world_dir / "chunks.dat").read_bytes()

    if len(data) < SECTOR_SIZE:
        raise ValueError(f"chunks.dat too small to be valid: {len(data)} bytes")

    # Location table: 1024 entries, indexed z*32 + x
    locations = struct.unpack_from("<1024I", data, 0)

    world = np.zeros(
        (WORLD_WIDTH, INTERNAL_HEIGHT, WORLD_DEPTH), dtype=np.uint8
    )

    for cz in range(WORLD_CHUNKS_Z):
        for cx in range(WORLD_CHUNKS_X):
            entry = locations[cz * 32 + cx]
            if entry == 0:
                continue  # chunk not present — leave as air
            sector_start = entry >> 8
            offset = sector_start * SECTOR_SIZE
            if offset + 4 > len(data):
                raise ValueError(
                    f"Chunk ({cx},{cz}) offset {offset} past EOF"
                )
            chunk_len = struct.unpack_from("<I", data, offset)[0]
            if chunk_len < 32768:
                raise ValueError(
                    f"Chunk ({cx},{cz}) too small: declared length {chunk_len}"
                )
            blocks_buf = data[offset + 4 : offset + 4 + 32768]
            # Layout: index = (x*16 + z)*128 + y, so reshape as (x, z, y)
            blocks_xzy = np.frombuffer(blocks_buf, dtype=np.uint8).reshape(
                CHUNK_BLOCKS_X, CHUNK_BLOCKS_Z, INTERNAL_HEIGHT
            )
            # Slice into world as [x, y, z]
            world[
                cx * 16 : (cx + 1) * 16,
                :,
                cz * 16 : (cz + 1) * 16,
            ] = blocks_xzy.transpose(0, 2, 1)

    return world
