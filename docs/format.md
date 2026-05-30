# MCPI `chunks.dat` format notes

The Minecraft: Pi Edition world format is a stripped-down clone of Pocket
Edition 0.6.x (circa 2013). It predates LevelDB and Anvil. There is no
official documentation; everything below is reverse-engineered from real
saves and cross-checked against [pymclevel's pocket.py][pymclevel].

## File layout

```
0x0000 ─┬─ Location table  (4096 bytes, 1024 * BE uint32)
        │      entry[i] = (sector_offset << 8) | sector_count
        │      i = z*32 + x  (Anvil-style addressing, even though MCPI
        │      only uses x=0..15, z=0..15 — other slots are zero)
0x1000 ─┴─ Chunk data, packed back-to-back in 4096-byte sectors
              each chunk occupies 21 sectors = 86016 bytes
              of which the first 4 are the LE uint32 length prefix
              (always 82176 in real saves) and the rest is content.
```

## Per-chunk content (after the 4-byte length prefix)

```
+0x00000  blocks       32768 B   uint8, index = (x*16 + z)*128 + y
+0x08000  data         16384 B   nibble, same index, low nibble = even y
+0x0C000  skyLight     16384 B   nibble
+0x10000  blockLight   16384 B   nibble
+0x14000  dirtyCols      256 B   uint8 per (x, z) column
+0x14100  (padding/reserved to 0x1500 = 5376 bytes per sub-section,
           x16 sub-sections = 86016 bytes total per chunk slot)
```

* **Block iteration order is XZY with Y innermost.** A 128-byte run at offsets
  `(x, z, 0..127)` is one full vertical column.
* **The Y range is 128 cells.** MCPI gameplay only uses y=0..63 (the build
  ceiling) but the storage is the full 128. Anything the player placed above
  y=63 — usually visible as "out of bounds" decoration — is in the upper
  half of each chunk. Don't ignore it.
* The data nibble encodes block subtype: wool color, slab variant, log
  rotation, stair facing, door half, etc. This loader currently discards it.

## How chunks are addressed

The location table is 1024 entries (32 * 32) even though MCPI's world is only
16 chunks square. Entries at `(x >= 16) || (z >= 16)` are zero. To read chunk
`(cx, cz)`:

```python
entry = locations[cz * 32 + cx]
if entry == 0:
    chunk_is_air  # not present
else:
    sector_start = entry >> 8
    sector_count = entry & 0xFF   # always 21 for MCPI
    file_offset  = sector_start * 4096
    length       = u32_le(file[file_offset:file_offset+4])
    block_buf    = file[file_offset+4 : file_offset+4+length]
```

## Companion files in an MCPI world directory

```
chunks.dat       blocks + light + heightmap (this doc)
level.dat        NBT — spawn position, gametype, seed
entities.dat     NBT — mobs, items, tile entities (chest contents, sign text)
```

`entities.dat` is a separately gzipped NBT compound. It's small (often <10 KB)
and contains a `TileEntities` list keyed by block coordinate, plus an
`Entities` list of dropped items and mobs. Parsing it lets you recover chest
contents and sign text. mcpi-revive doesn't yet — TODO.

[pymclevel]: https://github.com/mcedit/pymclevel/blob/master/pocket.py
