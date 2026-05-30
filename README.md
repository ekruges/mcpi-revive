# mcpi-revive

Convert Minecraft: Pi Edition worlds to modern Minecraft Java.

    pip install git+https://github.com/ekruges/mcpi-revive
    mcpi-revive <mcpi-world> <output> --install-to-saves

Open Minecraft, the world is in the list.


## Features

  - Reads MCPI `chunks.dat` (all 256 chunks, full y=0..127)
  - Decodes the data nibble:
      wool color, log axis, leaves variant,
      slab/double-slab variant + half, stair facing + half,
      doors (oak + iron), trapdoor, ladder, chest + furnace facing,
      bed, torch, redstone torch, quartz pillar axis,
      water/lava level, wheat/cactus/sugar-cane age, snow layers,
      cake bites, pumpkin/jack-o-lantern facing
  - 70+ block types mapped to vanilla Java IDs
  - Outputs modern (DataVersion 4790, 1.21+) Anvil with proper
    PalettedContainer sizing, 9-bit heightmaps, structures stub
  - Voids the surroundings — no modern terrain bleeds in around the
    MCPI footprint
  - Shifts the world so MCPI bedrock lands at y=-64
  - Spawn + seed pulled from MCPI's level.dat (little-endian PE NBT)
  - Deterministic output — same input, byte-identical .mca


## Requirements

Python 3.10+ and Minecraft Java installed locally (it borrows a
level.dat from one of your existing saves). Make a fresh world in
Minecraft if you don't have any saves yet.


## Usage

    mcpi-revive SOURCE DEST [--name NAME] [--template PATH]
                            [--install-to-saves] [--spawn X,Y,Z] [--no-void]

  SOURCE              MCPI world folder OR parent folder of several
                      (e.g. com.mojang/minecraftWorlds)
  DEST                output directory
  --template PATH     Java save to use as scaffold (auto-detected)
  --name NAME         world name in MC's world list
  --install-to-saves  also copy result into your MC saves directory
  --spawn X,Y,Z       override spawn point
  --no-void           leave the modern world generator running


## Library use

    from mcpi_revive import convert
    convert(
        "/path/to/mcpi/world",
        "/path/to/output",
        template_world="/path/to/.minecraft/saves/AnyWorld",
    )

    from mcpi_revive import parse_chunks_dat
    blocks = parse_chunks_dat("/path/to/mcpi/world")
    # (256, 128, 256) uint8 array of MCPI block ids


## How it works

  docs/format.md        the MCPI chunks.dat layout
  src/mcpi_revive/anvil.py    the modern Java chunk + region writer
  src/mcpi_revive/blocks.py   block id + data nibble mapping
  src/mcpi_revive/worldgen.py the void WorldGenSettings


## License

MIT.
