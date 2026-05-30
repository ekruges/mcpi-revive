# mcpi-revive

> Open your old Minecraft: Pi Edition worlds in modern Minecraft Java.

You found an old Raspberry Pi in a drawer. Its SD card still has the worlds
you built with your kid in 2018, on Mojang's free *Minecraft: Pi Edition*.
The Pi-Edition client is long gone, modern Minecraft can't read its save
format, every editor that ever supported it (MCEdit, MCEdit-Unified, Amulet,
Chunker) either doesn't run on Windows 11 or never knew about the
`chunks.dat` layout. **mcpi-revive** is the missing converter.

```bash
pip install mcpi-revive
mcpi-revive ./my-old-mcpi-world ./recovered-world --install-to-saves
```

Launch Minecraft, your old world is in the world list. That's it.

## What survives the trip

| Thing | Status |
| --- | --- |
| Terrain — every block from y=0 (bedrock) to y=127 (above MCPI's playable ceiling) | ✅ |
| Block types — the 45 vanilla MCPI IDs are mapped to modern Java names | ✅ |
| Builds above sea level (towers, floating bases) | ✅ — the loader reads MCPI's full 128-tall internal storage |
| Wool color, slab variant, stair facing, log rotation | ❌ — lives in MCPI's data nibble, dropped for now |
| Chest contents, sign text, mob positions | ❌ — they're in `entities.dat`, not yet parsed |
| Per-block light values | ❌ — Minecraft recomputes on load |

Unknown block IDs (a couple of bytes that MCPI used internally but aren't in
the public block list) come out as `minecraft:magenta_wool` — deliberately
ugly so you can spot them and re-map.

## What you need

* **Python 3.10+**
* **Modern Minecraft Java Edition installed locally.** mcpi-revive borrows the
  scaffolding (`level.dat`, `data/world_gen_settings.dat`, datapack stubs)
  from one of your existing saves. The easiest thing is to create a fresh
  blank world in Minecraft first; mcpi-revive will auto-detect it.

## Usage

### Convert one world

```bash
mcpi-revive path/to/mcpi/world ./out --name "Pi World"
```

### Convert every world under a Pi `minecraftWorlds/` directory

Point the source at the parent folder:

```bash
mcpi-revive /mnt/sdcard/home/pi/.minecraft/games/com.mojang/minecraftWorlds ./out
```

Each subfolder becomes its own converted save in `./out/`.

### Drop straight into Minecraft's saves

Append `--install-to-saves`:

```bash
mcpi-revive ./world- ./recovered --name "Pi World 2" --install-to-saves
```

It copies the converted world into `%APPDATA%/.minecraft/saves/` (or the
macOS/Linux equivalent) so it shows up next time you launch the game.

### Other flags

```
--template PATH     A specific Java save to use as a structural template.
                    Default: most-recently-modified save in your MC install.
--spawn X,Y,Z       Where the player spawns. Default 128,70,128 (middle of
                    the world, just above sea level).
-v / --verbose      Log every step.
```

## Library use

```python
from mcpi_revive import convert

convert(
    "/path/to/mcpi/world",
    "/path/to/output",
    level_name="Pi World",
    template_world="/path/to/.minecraft/saves/SomeFreshWorld",
)
```

You can also use the parser independently:

```python
from mcpi_revive import parse_chunks_dat
blocks = parse_chunks_dat("/path/to/mcpi/world")
# blocks is a (256, 128, 256) numpy array of MCPI block ids
```

## How it works

1. **Parse `chunks.dat`** using the [reverse-engineered MCPI format](docs/format.md).
   The file is a sector-based archive with a 4 KiB location table indexing
   256 chunks of 21 sectors each.
2. **Translate block IDs** through a 45-entry mapping table to modern Java
   namespaced names.
3. **Build modern (1.18+) Java chunk NBT** — flat root, lowercase `sections`,
   `block_states` compound with palette + properly-sized packed long array
   (Mojang's `PalettedContainer` is *very* strict about the exact length
   formula `ceil(4096 / floor(64 / bits))`), 9-bit Heightmaps, structures
   stub, etc.
4. **Pack a 1 MiB region file** at `dimensions/minecraft/overworld/region/r.0.0.mca`
   covering all 16x16 chunks at world coords (0..255, 0..255).
5. **Scaffold** `level.dat`, `data/world_gen_settings.dat`, datapack stubs,
   etc. from a real Java save — modern Minecraft expects these as separate
   files now, not just fields in `level.dat`.

See `docs/format.md` for the MCPI side and the doc-comments in `src/mcpi_revive/anvil.py`
for the Java side. Both files are intentionally small; you can read them.

## Why this doesn't already exist

Minecraft: Pi Edition was free, not officially supported, and its
`chunks.dat` format was abandoned by 2014 in favor of Pocket Edition's
LevelDB. The handful of contemporary tools (MCEdit "Original", pymclevel)
that supported it are Python-2-only and don't run on Windows 11. Modern
editors (Amulet, Chunker) inherited Bedrock's LevelDB code path and
skipped the chunks.dat era entirely. mcpi-revive fills that gap.

## Roadmap

- [ ] Parse the data nibble so wool colors, slab variants, log rotation, stair
      facing all survive.
- [ ] Parse `entities.dat` for chest contents, sign text, beds, dropped items.
- [ ] Support converting to Bedrock Edition (`.mcworld`) as well as Java.
- [ ] Bundle a minimal Java world template so a Minecraft install isn't
      strictly required.

## Acknowledgements

* [pymclevel/pocket.py](https://github.com/mcedit/pymclevel/blob/master/pocket.py)
  — the only working public documentation of the MCPI/Pocket-0.6 format.
* [Minecraft Wiki: Chunk format](https://minecraft.wiki/w/Chunk_format) and
  [Region file format](https://minecraft.wiki/w/Region_file_format) — the
  closest thing to a spec for modern Anvil.
* The [twoolie/NBT](https://github.com/twoolie/NBT) Python NBT library, which
  does all the actual byte-pushing for the Java side.

## License

MIT — see [LICENSE](LICENSE).
