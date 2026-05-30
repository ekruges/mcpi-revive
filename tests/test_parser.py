"""Parser smoke tests. Set MCPI_TEST_WORLD to enable."""
import os
from pathlib import Path

import numpy as np
import pytest

from mcpi_revive.parser import INTERNAL_HEIGHT, WORLD_DEPTH, WORLD_WIDTH, parse_chunks_dat


def _world():
    p = os.environ.get("MCPI_TEST_WORLD")
    return Path(p) if p else None


@pytest.mark.skipif(_world() is None, reason="no MCPI_TEST_WORLD")
def test_shape():
    w = parse_chunks_dat(_world())
    assert w.shape == (WORLD_WIDTH, INTERNAL_HEIGHT, WORLD_DEPTH)
    assert w.dtype == np.uint8


@pytest.mark.skipif(_world() is None, reason="no MCPI_TEST_WORLD")
def test_bedrock_at_y0():
    w = parse_chunks_dat(_world())
    assert (w[:, 0, :] == 7).all()
