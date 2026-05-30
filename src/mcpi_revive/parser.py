"""MCPI chunks.dat parser. Format notes in docs/format.md."""
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

WORLD_WIDTH = WORLD_CHUNKS_X * CHUNK_BLOCKS_X
WORLD_DEPTH = WORLD_CHUNKS_Z * CHUNK_BLOCKS_Z
WORLD_HEIGHT = INTERNAL_HEIGHT


def parse_chunks_dat(world_dir: Union[str, Path]) -> np.ndarray:
    """Read a world dir's chunks.dat into a (256, 128, 256) uint8 array [x, y, z]."""
    world_dir = Path(world_dir)
    data = (world_dir / "chunks.dat").read_bytes()

    if len(data) < SECTOR_SIZE:
        raise ValueError(f"chunks.dat too small: {len(data)} bytes")

    locations = struct.unpack_from("<1024I", data, 0)
    world = np.zeros((WORLD_WIDTH, INTERNAL_HEIGHT, WORLD_DEPTH), dtype=np.uint8)

    for cz in range(WORLD_CHUNKS_Z):
        for cx in range(WORLD_CHUNKS_X):
            entry = locations[cz * 32 + cx]
            if entry == 0:
                continue
            offset = (entry >> 8) * SECTOR_SIZE
            chunk_len = struct.unpack_from("<I", data, offset)[0]
            if chunk_len < 32768:
                raise ValueError(f"chunk ({cx},{cz}) too small: {chunk_len}")
            blocks = np.frombuffer(
                data[offset + 4 : offset + 4 + 32768], dtype=np.uint8
            ).reshape(CHUNK_BLOCKS_X, CHUNK_BLOCKS_Z, INTERNAL_HEIGHT)
            # MCPI is x*16+z columns, y inner -> transpose to [x, y, z]
            world[cx * 16 : (cx + 1) * 16, :, cz * 16 : (cz + 1) * 16] = blocks.transpose(0, 2, 1)

    return world
