# mcpi-revive

Open old **Minecraft: Pi Edition** worlds in modern Minecraft Java.

```bash
pip install git+https://github.com/ekruges/mcpi-revive
mcpi-revive ./my-old-mcpi-world ./recovered --install-to-saves
```

Launch Minecraft, your old world is in the list.

## Requirements

- Python 3.10+
- Minecraft Java installed locally (it borrows a `level.dat` from one of your existing saves — just make a new world first if you don't have one)

## What works

- All terrain blocks, including builds above MCPI's gameplay ceiling (y=64..127)
- 45 vanilla block types
- Block state from the data nibble: wool color, slab variant, stair facing, log axis, door state, trapdoor, ladder, chest/furnace facing, quartz pillar axis, water/lava level
- MCPI bedrock lands at modern y=-64 (matches the modern world floor)
- World spawn pulled from MCPI's `level.dat`
- Everything outside the 256×256 MCPI footprint is **void** — no modern terrain bleeding in

## What doesn't (yet)

- Chest contents, sign text (in MCPI's chunk tile-entity records / `entities.dat`, not parsed)
- Mobs and dropped items
- Player inventory
- A few obscure PE-exclusive blocks come out as magenta wool — easy to spot and re-map

## CLI

```
mcpi-revive <source> <output> [--name NAME] [--template PATH]
                              [--install-to-saves] [--spawn X,Y,Z] [--no-void]
```

`<source>` is either a single MCPI world folder or a parent containing several (e.g. `com.mojang/minecraftWorlds`).

## How it works

[`docs/format.md`](docs/format.md) covers MCPI's `chunks.dat`. The output side
is the modern flat 1.18+ chunk NBT — see `src/mcpi_revive/anvil.py`.

MIT.
