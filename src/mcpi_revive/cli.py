"""mcpi-revive CLI."""
from __future__ import annotations

import argparse
import logging
import os
import shutil
import sys
from pathlib import Path
from typing import Iterable, Optional

from . import __version__
from .convert import convert


def _default_minecraft_dir() -> Optional[Path]:
    if sys.platform.startswith("win"):
        ap = os.environ.get("APPDATA")
        if ap:
            p = Path(ap) / ".minecraft"
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


def _find_template(saves_dir: Path) -> Optional[Path]:
    if not saves_dir.is_dir():
        return None
    cands = [d for d in saves_dir.iterdir() if d.is_dir() and (d / "level.dat").exists()]
    return max(cands, key=lambda p: (p / "level.dat").stat().st_mtime) if cands else None


def _iter_worlds(src: Path) -> Iterable[Path]:
    if (src / "chunks.dat").is_file():
        yield src
        return
    for child in sorted(src.iterdir()):
        if child.is_dir() and (child / "chunks.dat").is_file():
            yield child


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="mcpi-revive")
    p.add_argument("--version", action="version", version=f"mcpi-revive {__version__}")
    p.add_argument("source", help="MCPI world dir, or parent dir of several")
    p.add_argument("dest", help="output dir")
    p.add_argument("--template", help="Java save dir to clone (auto-detected if omitted)")
    p.add_argument("--name", help="LevelName")
    p.add_argument("--install-to-saves", action="store_true",
                   help="also copy result into your MC saves")
    p.add_argument("--spawn", help="X,Y,Z (default: read from MCPI level.dat)")
    p.add_argument("--no-void", action="store_true",
                   help="Skip void world generator (leave default modern terrain outside).")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s  %(message)s", datefmt="%H:%M:%S",
    )

    src = Path(args.source)
    dest = Path(args.dest)
    if not src.exists():
        p.error(f"source not found: {src}")

    template = Path(args.template) if args.template else None
    if template is None:
        mc = _default_minecraft_dir()
        if mc:
            template = _find_template(mc / "saves")
        if template is None:
            p.error("no template found; pass --template")
        logging.info("template: %s", template)

    spawn = None
    if args.spawn:
        try:
            spawn = tuple(int(x) for x in args.spawn.split(","))
            if len(spawn) != 3:
                raise ValueError
        except ValueError:
            p.error("--spawn must be X,Y,Z ints")

    worlds = list(_iter_worlds(src))
    if not worlds:
        p.error(f"no MCPI worlds under {src}")

    dest.mkdir(parents=True, exist_ok=True)
    single = (src / "chunks.dat").is_file()

    for world in worlds:
        out = dest if single else dest / world.name
        name = args.name if args.name else world.name
        logging.info("converting %s -> %s", world.name, out)
        convert(
            world, out,
            level_name=args.name if args.name else None,
            template_world=template,
            spawn=spawn,
            void_surroundings=not args.no_void,
        )

        if args.install_to_saves:
            mc = _default_minecraft_dir()
            if not mc:
                logging.warning("no MC install found")
                continue
            target = mc / "saves" / name
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(out, target)
            logging.info("installed: %s", target)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
