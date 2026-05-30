"""Minimal library example: convert one MCPI world to a Java save."""
from mcpi_revive import convert

convert(
    mcpi_world_dir="/path/to/mcpi/world",
    out_dir="/path/to/output",
    level_name="My Old World",
    template_world="/path/to/.minecraft/saves/AnyFreshWorld",
)
