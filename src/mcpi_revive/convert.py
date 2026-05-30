"""MCPI world dir -> Java save dir."""
from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import Optional

import numpy as np
from nbt import nbt

from .anvil import (
    DATA_VERSION_DEFAULT,
    build_chunk_nbt,
    build_section,
    write_empty_region,
    write_region,
)
from .blocks import mcpi_to_java_name
from .parser import INTERNAL_HEIGHT, WORLD_CHUNKS_X, WORLD_CHUNKS_Z, parse_chunks_dat

log = logging.getLogger(__name__)

MIN_SECTION_Y = -4
MAX_SECTION_Y = 19
MIN_WORLD_Y = MIN_SECTION_Y * 16


def _block_id_lookup(world_blocks: np.ndarray) -> np.ndarray:
    lut = np.array([mcpi_to_java_name(i) for i in range(256)], dtype=object)
    return lut[world_blocks]


def _compute_highest_solid(world_blocks: np.ndarray) -> np.ndarray:
    nonair = world_blocks != 0  # (X, Y, Z)
    flipped = nonair[:, ::-1, :]
    any_y = flipped.any(axis=1)
    first_top = flipped.argmax(axis=1)
    top_y = (INTERNAL_HEIGHT - 1) - first_top
    return np.where(any_y, top_y, -1)


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


def _patch_level_dat(path: Path, level_name: str, spawn: tuple[int, int, int]) -> None:
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
    level_name: str = "MCPI Recovered",
    template_world: Optional[os.PathLike] = None,
    spawn: tuple[int, int, int] = (128, 70, 128),
    data_version: int = DATA_VERSION_DEFAULT,
) -> Path:
    if template_world is None:
        raise ValueError("template_world is required — pass a fresh Java save dir")

    mcpi_world_dir = Path(mcpi_world_dir)
    out_dir = Path(out_dir)

    log.info("cloning template")
    if out_dir.exists():
        shutil.rmtree(out_dir)
    _scaffold_from_template(Path(template_world), out_dir)

    log.info("parsing chunks.dat")
    world_blocks = parse_chunks_dat(mcpi_world_dir)
    java_names = _block_id_lookup(world_blocks)
    highest = _compute_highest_solid(world_blocks)

    log.info("building chunks")
    chunks: dict[tuple[int, int], nbt.NBTFile] = {}
    for cx in range(WORLD_CHUNKS_X):
        for cz in range(WORLD_CHUNKS_Z):
            sections = []
            for sy in range(MIN_SECTION_Y, MAX_SECTION_Y + 1):
                base = sy * 16
                if 0 <= base and base + 16 <= INTERNAL_HEIGHT:
                    block_slice = java_names[
                        cx * 16 : (cx + 1) * 16,
                        base : base + 16,
                        cz * 16 : (cz + 1) * 16,
                    ]
                else:
                    block_slice = np.full((16, 16, 16), "air", dtype=object)
                sections.append(build_section(sy, block_slice))
            chunks[(cx, cz)] = build_chunk_nbt(
                cx, cz,
                sections=sections,
                min_section_y=MIN_SECTION_Y,
                highest_solid_y=highest[cx * 16 : (cx + 1) * 16, cz * 16 : (cz + 1) * 16],
                min_world_y=MIN_WORLD_Y,
                data_version=data_version,
            )

    log.info("writing region")
    region_root = out_dir / "dimensions" / "minecraft" / "overworld"
    write_region(region_root / "region" / "r.0.0.mca", chunks)
    write_empty_region(region_root / "entities" / "r.0.0.mca")
    write_empty_region(region_root / "poi" / "r.0.0.mca")

    log.info("patching level.dat")
    _patch_level_dat(out_dir / "level.dat", level_name, spawn)
    (out_dir / "session.lock").write_bytes(b"\xe2\x98\x83")

    log.info("done: %s", out_dir)
    return out_dir
