"""Void overworld WorldGenSettings.

Modern MC (~26.1+) keeps WGS in `data/minecraft/world_gen_settings.dat`.
That file's root layout is:

    Root TAG_Compound (unnamed)
      data         TAG_Compound — children seed / bonus_chest /
                                   generate_structures / dimensions
      DataVersion  TAG_Int

The inline `level.dat:Data.WorldGenSettings` field has been removed from the
modern level.dat schema, so we don't bother patching it.

The flat-world generator with biome `minecraft:the_void` and empty layers is
the canonical "no terrain" config; the player can't see Nether or End from a
void overworld so we leave those at their defaults.
"""
from __future__ import annotations

from pathlib import Path

from nbt import nbt


def _str(name: str, value: str) -> nbt.TAG_String:
    t = nbt.TAG_String(value=value); t.name = name; return t


def _byte(name: str, value: int) -> nbt.TAG_Byte:
    t = nbt.TAG_Byte(value=value); t.name = name; return t


def _int(name: str, value: int) -> nbt.TAG_Int:
    t = nbt.TAG_Int(value=value); t.name = name; return t


def _long(name: str, value: int) -> nbt.TAG_Long:
    t = nbt.TAG_Long(value=value); t.name = name; return t


def _compound(name: str, *tags) -> nbt.TAG_Compound:
    c = nbt.TAG_Compound(); c.name = name
    for t in tags:
        c.tags.append(t)
    return c


def _flat_overworld_settings() -> nbt.TAG_Compound:
    settings = nbt.TAG_Compound(); settings.name = "settings"
    settings.tags.append(_str("biome", "minecraft:the_void"))
    settings.tags.append(_byte("features", 0))
    settings.tags.append(_byte("lakes", 0))
    settings.tags.append(nbt.TAG_List(name="layers", type=nbt.TAG_Compound))
    settings.tags.append(nbt.TAG_List(name="structure_overrides", type=nbt.TAG_String))
    return settings


def build_wgs_inner(seed: int = 0) -> list:
    """Children of the `data` compound in world_gen_settings.dat."""
    children = []
    children.append(_long("seed", seed))
    children.append(_byte("bonus_chest", 0))
    children.append(_byte("generate_structures", 0))

    dimensions = nbt.TAG_Compound(); dimensions.name = "dimensions"
    dimensions.tags.append(_compound(
        "minecraft:overworld",
        _str("type", "minecraft:overworld"),
        _compound(
            "generator",
            _str("type", "minecraft:flat"),
            _flat_overworld_settings(),
        ),
    ))
    dimensions.tags.append(_compound(
        "minecraft:the_nether",
        _str("type", "minecraft:the_nether"),
        _compound(
            "generator",
            _str("type", "minecraft:noise"),
            _compound(
                "biome_source",
                _str("type", "minecraft:multi_noise"),
                _str("preset", "minecraft:nether"),
            ),
            _str("settings", "minecraft:nether"),
        ),
    ))
    dimensions.tags.append(_compound(
        "minecraft:the_end",
        _str("type", "minecraft:the_end"),
        _compound(
            "generator",
            _str("type", "minecraft:noise"),
            _compound("biome_source", _str("type", "minecraft:the_end")),
            _str("settings", "minecraft:end"),
        ),
    ))
    children.append(dimensions)
    return children


def install_void_worldgen(world_dir: Path, seed: int = 0, data_version: int = 4790) -> None:
    """Write `data/minecraft/world_gen_settings.dat` with a void overworld."""
    world_dir = Path(world_dir)

    # Strip any stale WorldGenSettings from level.dat (modern MC doesn't read it
    # from there, and leftover wrong-shape data confuses serializers in some
    # tools).
    level_path = world_dir / "level.dat"
    if level_path.exists():
        f = nbt.NBTFile(str(level_path))
        try:
            data = f["Data"]
            data.tags = [t for t in data.tags if t.name != "WorldGenSettings"]
            f.write_file(str(level_path))
        except KeyError:
            pass

    wgs_dir = world_dir / "data" / "minecraft"
    wgs_dir.mkdir(parents=True, exist_ok=True)

    root = nbt.NBTFile()
    data_wrapper = nbt.TAG_Compound(); data_wrapper.name = "data"
    for child in build_wgs_inner(seed):
        data_wrapper.tags.append(child)
    root.tags.append(data_wrapper)
    root.tags.append(_int("DataVersion", data_version))
    root.write_file(str(wgs_dir / "world_gen_settings.dat"))
