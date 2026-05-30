"""MCPI chunks.dat parser. Format notes in docs/format.md."""
from __future__ import annotations

import struct
from pathlib import Path
from typing import Optional, Tuple, Union

import numpy as np
from nbt import nbt

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
    """Block IDs only. Returns (256, 128, 256) uint8 array [x, y, z]."""
    blocks, _ = parse_blocks_and_data(world_dir)
    return blocks


def parse_blocks_and_data(world_dir: Union[str, Path]) -> Tuple[np.ndarray, np.ndarray]:
    """Block IDs + decoded data nibble. Both shape (256, 128, 256) uint8."""
    world_dir = Path(world_dir)
    data = (world_dir / "chunks.dat").read_bytes()
    if len(data) < SECTOR_SIZE:
        raise ValueError(f"chunks.dat too small: {len(data)} bytes")

    locations = struct.unpack_from("<1024I", data, 0)
    blocks = np.zeros((WORLD_WIDTH, INTERNAL_HEIGHT, WORLD_DEPTH), dtype=np.uint8)
    metadata = np.zeros((WORLD_WIDTH, INTERNAL_HEIGHT, WORLD_DEPTH), dtype=np.uint8)

    for cz in range(WORLD_CHUNKS_Z):
        for cx in range(WORLD_CHUNKS_X):
            entry = locations[cz * 32 + cx]
            if entry == 0:
                continue
            offset = (entry >> 8) * SECTOR_SIZE
            chunk_len = struct.unpack_from("<I", data, offset)[0]
            if chunk_len < 32768 + 16384:
                raise ValueError(f"chunk ({cx},{cz}) too small: {chunk_len}")
            start = offset + 4
            b = np.frombuffer(data[start : start + 32768], dtype=np.uint8).reshape(
                CHUNK_BLOCKS_X, CHUNK_BLOCKS_Z, INTERNAL_HEIGHT
            )
            # Data nibble: 16384 bytes, low nibble = even y, high nibble = odd y
            packed = np.frombuffer(
                data[start + 32768 : start + 32768 + 16384], dtype=np.uint8
            ).reshape(CHUNK_BLOCKS_X, CHUNK_BLOCKS_Z, INTERNAL_HEIGHT // 2)
            unpacked = np.empty(
                (CHUNK_BLOCKS_X, CHUNK_BLOCKS_Z, INTERNAL_HEIGHT), dtype=np.uint8
            )
            unpacked[..., 0::2] = packed & 0x0F
            unpacked[..., 1::2] = (packed >> 4) & 0x0F

            blocks[cx * 16 : (cx + 1) * 16, :, cz * 16 : (cz + 1) * 16] = b.transpose(0, 2, 1)
            metadata[cx * 16 : (cx + 1) * 16, :, cz * 16 : (cz + 1) * 16] = unpacked.transpose(0, 2, 1)

    return blocks, metadata


def parse_level_dat(world_dir: Union[str, Path]) -> dict:
    """Read MCPI level.dat. Returns dict with name/spawn/seed/etc.

    MCPI's level.dat is little-endian NBT with an 8-byte PE header
    (storage_version, data_length), unlike Java's gzipped big-endian NBT.
    We parse it by hand.
    """
    p = Path(world_dir) / "level.dat"
    if not p.exists():
        return {}
    try:
        raw = p.read_bytes()
        if len(raw) < 8:
            return {}
        body = raw[8:]
        return _parse_le_nbt_root(body)
    except Exception:
        return {}


# Minimal little-endian NBT parser — only what we need from MCPI level.dat.

_TAG_END = 0
_TAG_BYTE = 1
_TAG_SHORT = 2
_TAG_INT = 3
_TAG_LONG = 4
_TAG_FLOAT = 5
_TAG_DOUBLE = 6
_TAG_BYTE_ARRAY = 7
_TAG_STRING = 8
_TAG_LIST = 9
_TAG_COMPOUND = 10
_TAG_INT_ARRAY = 11
_TAG_LONG_ARRAY = 12


def _parse_le_nbt_root(body: bytes) -> dict:
    pos = [0]

    def u8() -> int:
        v = body[pos[0]]; pos[0] += 1; return v

    def i16() -> int:
        v = int.from_bytes(body[pos[0]:pos[0]+2], "little", signed=True); pos[0] += 2; return v

    def u16() -> int:
        v = int.from_bytes(body[pos[0]:pos[0]+2], "little", signed=False); pos[0] += 2; return v

    def i32() -> int:
        v = int.from_bytes(body[pos[0]:pos[0]+4], "little", signed=True); pos[0] += 4; return v

    def i64() -> int:
        v = int.from_bytes(body[pos[0]:pos[0]+8], "little", signed=True); pos[0] += 8; return v

    def f32() -> float:
        import struct
        v = struct.unpack_from("<f", body, pos[0])[0]; pos[0] += 4; return v

    def f64() -> float:
        import struct
        v = struct.unpack_from("<d", body, pos[0])[0]; pos[0] += 8; return v

    def s() -> str:
        n = u16()
        v = body[pos[0]:pos[0]+n].decode("utf-8", errors="replace"); pos[0] += n; return v

    def read_payload(tag_type: int):
        if tag_type == _TAG_BYTE: return u8()
        if tag_type == _TAG_SHORT: return i16()
        if tag_type == _TAG_INT: return i32()
        if tag_type == _TAG_LONG: return i64()
        if tag_type == _TAG_FLOAT: return f32()
        if tag_type == _TAG_DOUBLE: return f64()
        if tag_type == _TAG_BYTE_ARRAY:
            n = i32()
            v = body[pos[0]:pos[0]+n]; pos[0] += n; return v
        if tag_type == _TAG_STRING: return s()
        if tag_type == _TAG_LIST:
            inner = u8()
            n = i32()
            return [read_payload(inner) for _ in range(n)]
        if tag_type == _TAG_COMPOUND:
            out: dict = {}
            while True:
                t = u8()
                if t == _TAG_END:
                    break
                name = s()
                out[name] = read_payload(t)
            return out
        if tag_type == _TAG_INT_ARRAY:
            n = i32()
            return [i32() for _ in range(n)]
        if tag_type == _TAG_LONG_ARRAY:
            n = i32()
            return [i64() for _ in range(n)]
        raise ValueError(f"unsupported tag type {tag_type}")

    # Root: TAG_Compound (named "")
    t = u8()
    name = s() if t != _TAG_END else ""
    if t != _TAG_COMPOUND:
        return {}
    root = read_payload(_TAG_COMPOUND)

    out: dict = {}
    out["LevelName"] = root.get("LevelName")
    out["GameType"] = root.get("GameType")
    out["Time"] = root.get("Time")
    out["LastPlayed"] = root.get("LastPlayed")
    out["RandomSeed"] = root.get("RandomSeed")
    sx, sy, sz = root.get("SpawnX"), root.get("SpawnY"), root.get("SpawnZ")
    if sx is not None and sy is not None and sz is not None:
        out["Spawn"] = (int(sx), int(sy), int(sz))
    try:
        pos = root["Player"]["Pos"]
        out["PlayerPos"] = tuple(float(v) for v in pos)
    except (KeyError, TypeError):
        pass
    return out
