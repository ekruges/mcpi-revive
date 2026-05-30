"""Use the parser without writing — get every block id from a world."""
import collections
from mcpi_revive import parse_chunks_dat

blocks = parse_chunks_dat("/path/to/mcpi/world")
hist = collections.Counter(blocks.flatten().tolist())
for bid, n in hist.most_common(20):
    print(f"id={bid:3d}  count={n}")
