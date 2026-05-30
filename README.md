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

- All terrain blocks, from bedrock to anything you built above sea level (MCPI stores up to y=127)
- 45 vanilla block types

## What doesn't (yet)

- Wool color / slab type / stair direction (in MCPI's data nibble, dropped)
- Chest contents, sign text, mobs (in `entities.dat`, not parsed)

Unknown block IDs come out as magenta wool — easy to spot.

## CLI

```
mcpi-revive <source> <output> [--name NAME] [--template PATH] [--install-to-saves] [--spawn X,Y,Z]
```

`<source>` is either a single MCPI world folder or a parent containing several (e.g. `com.mojang/minecraftWorlds`).

## How it works

[`docs/format.md`](docs/format.md) covers MCPI's `chunks.dat`. The output side
is the modern flat 1.18+ chunk NBT — see `src/mcpi_revive/anvil.py`.

MIT.
