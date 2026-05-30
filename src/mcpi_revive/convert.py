"""High-level orchestration: MCPI world dir -> playable Java save dir."""
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
from .parser import (
    INTERNAL_HEIGHT,
    WORLD_CHUNKS_X,
    WORLD_CHUNKS_Z,
    parse_chunks_dat,
)

log = logging.getLogger(__name__)

# Modern (1.18+) overworld bounds. yPos of every chunk = -4.
MIN_SECTION_Y = -4
MAX_SECTION_Y = 19
SECTIONS_PER_CHUNK = MAX_SECTION_Y - MIN_SECTION_Y + 1   # 24
MIN_WORLD_Y = MIN_SECTION_Y * 16   # -64


def _block_id_lookup(world_blocks: np.ndarray) -> np.ndarray:
    """Vectorised translation of MCPI ids to Java block names."""
    # numpy can't vectorise a python dict directly without numpy>=1.20 vectorize;
    # build a 256-entry lookup table.
    lut = np.array(
        [mcpi_to_java_name(i) for i in range(256)],
        dtype=object,
    )
    return lut[world_blocks]


def _compute_highest_solid(world_blocks: np.ndarray, world_y_offset: int = 0) -> np.ndarray:
    """Return (256, 256) int array of highest non-air *world Y* per (x, z).

    Columns that are entirely air get ``world_y_offset - 1`` so they encode as 0
    in the heightmap.
    """
    nonair = world_blocks != 0    # (X, Y, Z)
    # argmax from the top: highest y where block != 0
    # We flip Y, find first True, convert back to y index.
    flipped = nonair[:, ::-1, :]
    # any() across Y to know which columns have content
    any_y = flipped.any(axis=1)            # (X, Z)
    first_top = flipped.argmax(axis=1)     # (X, Z)
    top_y = (INTERNAL_HEIGHT - 1) - first_top
    # For all-air columns, encode below-min so heightmap encodes 0
    top_y = np.where(any_y, top_y + world_y_offset, world_y_offset - 1)
    return top_y


def _strip_chunk_files(world_root: Path) -> None:
    """Remove all .mca chunk files from a copied world template."""
    dims = world_root / "dimensions"
    if dims.exists():
        for mca in dims.rglob("*.mca"):
            mca.unlink()
    legacy = world_root / "region"
    if legacy.exists():
        for mca in legacy.rglob("*.mca"):
            mca.unlink()


def _scaffold_from_template(template: Path, dest: Path) -> None:
    """Clone a Java world to ``dest`` and strip its chunk and player data."""
    shutil.copytree(template, dest)
    _strip_chunk_files(dest)
    (dest / "session.lock").unlink(missing_ok=True)
    pdata = dest / "players" / "data"
    if pdata.exists():
        for f in pdata.iterdir():
            if f.is_file():
                f.unlink()


def _patch_level_dat(path: Path, level_name: str, spawn: tuple[int, int, int]) -> None:
    """Update the templated level.dat with our world name and spawn position."""
    f = nbt.NBTFile(str(path))
    data = f["Data"]
    names = {t.name for t in data.tags}

    def set_tag(name: str, tag_cls, value):
        if name in names:
            data[name].value = value
        else:
            t = tag_cls(value=value)
            t.name = name
            data.tags.append(t)
            names.add(name)

    set_tag("LevelName", nbt.TAG_String, level_name)
    set_tag("GameType", nbt.TAG_Int, 1)            # creative
    set_tag("allowCommands", nbt.TAG_Byte, 1)
    set_tag("initialized", nbt.TAG_Byte, 1)

    # Newer Minecraft (1.21+) uses a `spawn` compound with `pos: int_array`.
    # Older versions use SpawnX / SpawnY / SpawnZ.
    if "spawn" in names:
        sp = data["spawn"]
        pos_arr = nbt.TAG_Int_Array(name="pos")
        pos_arr.value = list(spawn)
        sp.tags = [t for t in sp.tags if t.name != "pos"] + [pos_arr]
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
    """Convert one MCPI world directory into a playable Java save directory.

    Args:
        mcpi_world_dir: Path to the MCPI world folder containing ``chunks.dat``.
        out_dir: Where to write the Java save. Will be ``rmtree``'d if it
            already exists.
        level_name: World name shown in Minecraft's world list.
        template_world: Path to an existing Java save directory used as a
            scaffold for ``level.dat``, ``data/``, ``datapacks/``, etc.
            *Required* — modern Minecraft expects a populated
            ``data/minecraft/world_gen_settings.dat`` etc. The easiest
            template is a brand-new world created in your current Minecraft.
        spawn: ``(x, y, z)`` world spawn position. Default is centered just
            above sea level.
        data_version: Java Data Version to advertise. Default matches MC
            26.1.2 / 1.21.x.

    Returns:
        The output directory path.
    """
    mcpi_world_dir = Path(mcpi_world_dir)
    out_dir = Path(out_dir)
    if template_world is None:
        raise ValueError(
            "template_world is required — pass a path to an existing Java "
            "world (e.g. a freshly-created one in your current MC) so we can "
            "scaffold level.dat / data/world_gen_settings.dat correctly."
        )

    log.info("Cloning template from %s", template_world)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    _scaffold_from_template(Path(template_world), out_dir)

    log.info("Parsing %s/chunks.dat", mcpi_world_dir)
    world_blocks = parse_chunks_dat(mcpi_world_dir)
    java_name_blocks = _block_id_lookup(world_blocks)
    highest_solid = _compute_highest_solid(world_blocks)

    log.info("Building chunks...")
    chunks: dict[tuple[int, int], nbt.NBTFile] = {}
    for cx in range(WORLD_CHUNKS_X):
        for cz in range(WORLD_CHUNKS_Z):
            sections = []
            for sy in range(MIN_SECTION_Y, MAX_SECTION_Y + 1):
                base = sy * 16
                if 0 <= base and base + 16 <= INTERNAL_HEIGHT:
                    block_slice = java_name_blocks[
                        cx * 16 : (cx + 1) * 16,
                        base : base + 16,
                        cz * 16 : (cz + 1) * 16,
                    ]
                else:
                    block_slice = np.full(
                        (16, 16, 16), "air", dtype=object
                    )
                sections.append(build_section(sy, block_slice))

            hsy_chunk = highest_solid[
                cx * 16 : (cx + 1) * 16,
                cz * 16 : (cz + 1) * 16,
            ]
            chunks[(cx, cz)] = build_chunk_nbt(
                cx, cz,
                sections=sections,
                min_section_y=MIN_SECTION_Y,
                highest_solid_y=hsy_chunk,
                min_world_y=MIN_WORLD_Y,
                data_version=data_version,
            )

    log.info("Writing region files...")
    region_root = out_dir / "dimensions" / "minecraft" / "overworld" / "region"
    write_region(region_root / "r.0.0.mca", chunks)
    # Empty placeholders for entities & poi
    write_empty_region(
        out_dir / "dimensions" / "minecraft" / "overworld" / "entities" / "r.0.0.mca"
    )
    write_empty_region(
        out_dir / "dimensions" / "minecraft" / "overworld" / "poi" / "r.0.0.mca"
    )

    log.info("Patching level.dat: name=%r spawn=%r", level_name, spawn)
    _patch_level_dat(out_dir / "level.dat", level_name, spawn)

    (out_dir / "session.lock").write_bytes(b"\xe2\x98\x83")

    log.info("Done: %s", out_dir)
    return out_dir
