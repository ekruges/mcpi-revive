"""Build a 'void overworld' WorldGenSettings so the converted world doesn't
have modern terrain bleeding in around the MCPI footprint.

Layout follows the vanilla `flat` world preset with biome = `the_void` and
empty layers. Nether and End use their standard noise generators (the player
can't see them from a void overworld anyway).

Modern MC (~26.1+) keeps this in `data/minecraft/world_gen_settings.dat`;
older versions keep it inline at `level.dat`'s `Data.WorldGenSettings`. We
write both for safety.
"""
from __future__ import annotations

from pathlib import Path

from nbt import nbt


def _str(name: str, value: str) -> nbt.TAG_String:
    t = nbt.TAG_String(value=value); t.name = name; return t


def _byte(name: str, value: int) -> nbt.TAG_Byte:
    t = nbt.TAG_Byte(value=value); t.name = name; return t


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
    layers = nbt.TAG_List(name="layers", type=nbt.TAG_Compound)
    settings.tags.append(layers)
    structure_overrides = nbt.TAG_List(name="structure_overrides", type=nbt.TAG_String)
    settings.tags.append(structure_overrides)
    return settings


def build_world_gen_settings(seed: int = 0) -> nbt.TAG_Compound:
    """Build the WorldGenSettings compound (named ``WorldGenSettings``)."""
    wgs = nbt.TAG_Compound(); wgs.name = "WorldGenSettings"
    wgs.tags.append(_long("seed", seed))
    wgs.tags.append(_byte("generate_features", 0))
    wgs.tags.append(_byte("bonus_chest", 0))

    dimensions = nbt.TAG_Compound(); dimensions.name = "dimensions"

    overworld = _compound(
        "minecraft:overworld",
        _str("type", "minecraft:overworld"),
        _compound(
            "generator",
            _str("type", "minecraft:flat"),
            _flat_overworld_settings(),
        ),
    )
    nether = _compound(
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
    )
    end = _compound(
        "minecraft:the_end",
        _str("type", "minecraft:the_end"),
        _compound(
            "generator",
            _str("type", "minecraft:noise"),
            _compound("biome_source", _str("type", "minecraft:the_end")),
            _str("settings", "minecraft:end"),
        ),
    )
    dimensions.tags.extend([overworld, nether, end])
    wgs.tags.append(dimensions)
    return wgs


def install_void_worldgen(world_dir: Path, seed: int = 0) -> None:
    """Replace `level.dat`'s WorldGenSettings AND write a standalone
    `data/minecraft/world_gen_settings.dat`."""
    world_dir = Path(world_dir)

    # 1. Patch level.dat in place
    level_path = world_dir / "level.dat"
    f = nbt.NBTFile(str(level_path))
    data = f["Data"]
    data.tags = [t for t in data.tags if t.name != "WorldGenSettings"]
    data.tags.append(build_world_gen_settings(seed))
    f.write_file(str(level_path))

    # 2. Standalone file for 26.1+. Root compound IS the WGS — children
    #    seed/generate_features/bonus_chest/dimensions go in directly.
    wgs_dir = world_dir / "data" / "minecraft"
    wgs_dir.mkdir(parents=True, exist_ok=True)
    standalone = nbt.NBTFile()
    for child in build_world_gen_settings(seed).tags:
        standalone.tags.append(child)
    standalone.write_file(str(wgs_dir / "world_gen_settings.dat"))
