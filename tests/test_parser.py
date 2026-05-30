"""Parser smoke tests.

These need a real MCPI world to exercise. If none is available the tests
are skipped — they're primarily for local verification.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest

from mcpi_revive.parser import (
    INTERNAL_HEIGHT,
    WORLD_DEPTH,
    WORLD_WIDTH,
    parse_chunks_dat,
)


def _local_world() -> Path | None:
    p = os.environ.get("MCPI_TEST_WORLD")
    return Path(p) if p else None


@pytest.mark.skipif(_local_world() is None, reason="no MCPI_TEST_WORLD env var")
def test_world_shape():
    world = parse_chunks_dat(_local_world())
    assert world.shape == (WORLD_WIDTH, INTERNAL_HEIGHT, WORLD_DEPTH)
    assert world.dtype == np.uint8


@pytest.mark.skipif(_local_world() is None, reason="no MCPI_TEST_WORLD env var")
def test_bedrock_at_y0():
    """Real MCPI worlds have bedrock=7 everywhere at y=0."""
    world = parse_chunks_dat(_local_world())
    assert (world[:, 0, :] == 7).all()
