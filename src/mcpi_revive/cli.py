"""CLI entry point: ``mcpi-revive``."""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Iterable, Optional

from .convert import convert
from . import __version__


def _default_minecraft_dir() -> Optional[Path]:
    """Best-effort guess at the user's Minecraft Java install root."""
    if sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA")
        if appdata:
            p = Path(appdata) / ".minecraft"
            if p.exists():
                return p
    elif sys.platform == "darwin":
        p = Path.home() / "Library" / "Application Support" / "minecraft"
        if p.exists():
            return p
    else:
        p = Path.home() / ".minecraft"
        if p.exists():
            return p
    return None


def _find_template_world(saves_dir: Path) -> Optional[Path]:
    """Find the most recently modified save to use as a level.dat template."""
    if not saves_dir.is_dir():
        return None
    candidates = [
        d for d in saves_dir.iterdir()
        if d.is_dir() and (d / "level.dat").exists()
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda p: (p / "level.dat").stat().st_mtime)


def _iter_mcpi_worlds(src: Path) -> Iterable[Path]:
    """Yield each MCPI world directory under ``src``.

    Accepts either a single world directory (containing chunks.dat) or a
    parent directory containing several.
    """
    if (src / "chunks.dat").is_file():
        yield src
        return
    for child in sorted(src.iterdir()):
        if child.is_dir() and (child / "chunks.dat").is_file():
            yield child


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mcpi-revive",
        description="Convert Minecraft: Pi Edition worlds into modern Java saves.",
    )
    parser.add_argument(
        "--version", action="version", version=f"mcpi-revive {__version__}"
    )
    parser.add_argument(
        "source",
        help=(
            "MCPI world directory containing chunks.dat, OR a parent folder "
            "containing several MCPI worlds (e.g. com.mojang/minecraftWorlds)."
        ),
    )
    parser.add_argument(
        "dest",
        help=(
            "Output directory. For a single source world, the converted save "
            "lands directly here. For multiple sources, each becomes a "
            "subdirectory."
        ),
    )
    parser.add_argument(
        "--template",
        help=(
            "Path to an existing Java save directory used as a structural "
            "template (level.dat, data/, datapacks/). If omitted, the most "
            "recently played save under your Minecraft installation is used."
        ),
    )
    parser.add_argument(
        "--name",
        help="LevelName shown in the world list. Defaults to source folder name.",
    )
    parser.add_argument(
        "--install-to-saves",
        action="store_true",
        help=(
            "Also copy the result into your Minecraft saves directory so it "
            "shows up immediately in the world list."
        ),
    )
    parser.add_argument(
        "--spawn",
        default="128,70,128",
        help="World spawn position as X,Y,Z. Default 128,70,128.",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Verbose logging."
    )

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s  %(message)s",
        datefmt="%H:%M:%S",
    )

    src = Path(args.source)
    dest = Path(args.dest)
    if not src.exists():
        parser.error(f"source not found: {src}")

    template = Path(args.template) if args.template else None
    if template is None:
        mc = _default_minecraft_dir()
        if mc:
            template = _find_template_world(mc / "saves")
        if template is None:
            parser.error(
                "Could not auto-detect a Java save template. Pass --template "
                "with the path to a fresh Java world (create one in MC first)."
            )
        logging.info("Using template: %s", template)

    try:
        spawn = tuple(int(p) for p in args.spawn.split(","))
        if len(spawn) != 3:
            raise ValueError
    except ValueError:
        parser.error(f"--spawn must be three integers like 128,70,128 (got {args.spawn!r})")

    worlds = list(_iter_mcpi_worlds(src))
    if not worlds:
        parser.error(f"no MCPI worlds found under {src}")

    dest.mkdir(parents=True, exist_ok=True)
    single = (src / "chunks.dat").is_file()

    for world in worlds:
        out_dir = dest if single else dest / world.name
        name = args.name if (single and args.name) else (args.name or world.name)
        logging.info("Converting %s -> %s", world.name, out_dir)
        convert(
            world,
            out_dir,
            level_name=name,
            template_world=template,
            spawn=spawn,  # type: ignore[arg-type]
        )

        if args.install_to_saves:
            mc = _default_minecraft_dir()
            if not mc:
                logging.warning("No Minecraft install found; skipping --install-to-saves")
            else:
                import shutil as _shutil

                dest_save = mc / "saves" / name
                if dest_save.exists():
                    _shutil.rmtree(dest_save)
                _shutil.copytree(out_dir, dest_save)
                logging.info("Installed to %s", dest_save)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
