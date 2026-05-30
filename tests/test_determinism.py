"""Same chunks in -> same region bytes out."""
import io
import zlib

from mcpi_revive.anvil import build_chunk_nbt, build_section, write_region
import numpy as np


def _trivial_chunk(cx, cz):
    air = ("air", {})
    states = np.empty((16, 16, 16), dtype=object)
    states[:] = [[[air] * 16] * 16] * 16
    sections = [build_section(sy, states) for sy in range(-4, 20)]
    hsy = np.full((16, 16), -100, dtype=int)
    return build_chunk_nbt(
        cx, cz,
        sections=sections,
        min_section_y=-4,
        highest_solid_y=hsy,
        min_world_y=-64,
    )


def test_region_bytes_are_deterministic(tmp_path):
    chunks = {(cx, cz): _trivial_chunk(cx, cz) for cx in range(4) for cz in range(4)}
    p1 = tmp_path / "r1.mca"
    p2 = tmp_path / "r2.mca"
    write_region(p1, chunks)
    write_region(p2, chunks)
    assert p1.read_bytes() == p2.read_bytes()


def test_region_iteration_order_doesnt_matter(tmp_path):
    """Region writer sorts chunks internally — passing them in different orders
    produces the same bytes."""
    forward = {(cx, cz): _trivial_chunk(cx, cz) for cx in range(2) for cz in range(2)}
    reverse = dict(reversed(list(forward.items())))
    p1 = tmp_path / "fwd.mca"
    p2 = tmp_path / "rev.mca"
    write_region(p1, forward)
    write_region(p2, reverse)
    assert p1.read_bytes() == p2.read_bytes()
