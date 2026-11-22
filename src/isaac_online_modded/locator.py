"""Locate the game executable, Steam libraries and the mods directory."""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path
from typing import Iterable


GAME_DIR_NAME = "The Binding of Isaac Rebirth"
GAME_EXE_NAME = "isaac-ng.exe"


def expand_path(value: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(value)))


def unique_paths(paths: Iterable[Path]) -> list[Path]:
    seen: set[str] = set()
    result: list[Path] = []
    for path in paths:
        key = str(path)
        if key not in seen:
            seen.add(key)
            result.append(path)
    return result


def steam_roots() -> list[Path]:
    home = Path.home()
    candidates = [
        os.environ.get("STEAM_ROOT"),
        os.environ.get("STEAM_DIR"),
        os.environ.get("STEAM_COMPAT_CLIENT_INSTALL_PATH"),
    ]
    paths = [expand_path(p) for p in candidates if p]
    paths.extend(
        [
            home / ".local/share/Steam",
            home / ".steam/steam",
            home / ".var/app/com.valvesoftware.Steam/.local/share/Steam",
        ]
    )
    return unique_paths(paths)


def unescape_vdf_path(value: str) -> str:
    return value.replace("\\\\", "\\").replace('\\"', '"')


def steam_library_roots(steam_root: Path) -> list[Path]:
    paths = [steam_root]
    vdf_path = steam_root / "steamapps/libraryfolders.vdf"
    if not vdf_path.exists():
        return unique_paths(paths)

    text = vdf_path.read_text(encoding="utf-8", errors="replace")

    for raw in re.findall(r'"path"\s+"((?:\\.|[^"\\])*)"', text):
        paths.append(expand_path(unescape_vdf_path(raw)))

    # Old libraryfolders.vdf format used numeric keys directly as paths.
    for raw in re.findall(r'"\d+"\s+"((?:\\.|[^"\\])*)"', text):
        candidate = unescape_vdf_path(raw)
        if candidate.startswith(("/", "~", "$")):
            paths.append(expand_path(candidate))

    return unique_paths(paths)


def candidate_game_dirs() -> list[Path]:
    paths: list[Path] = []
    env_game_dir = os.environ.get("ISAAC_GAME_DIR")
    if env_game_dir:
        paths.append(expand_path(env_game_dir))

    for steam_root in steam_roots():
        for library_root in steam_library_roots(steam_root):
            paths.append(library_root / "steamapps/common" / GAME_DIR_NAME)

    return unique_paths(paths)


def detect_game_exe(args: argparse.Namespace) -> Path:
    """Resolve the executable from arguments, environment or Steam libraries."""

    if args.game_exe:
        return expand_path(args.game_exe)

    if args.game_dir:
        return expand_path(args.game_dir) / GAME_EXE_NAME

    if args.path:
        path = expand_path(args.path)
        if path.name.lower() == GAME_EXE_NAME or (path.exists() and path.is_file()):
            return path
        return path / GAME_EXE_NAME

    env_game_exe = os.environ.get("ISAAC_GAME_EXE")
    if env_game_exe:
        return expand_path(env_game_exe)

    for game_dir in candidate_game_dirs():
        exe = game_dir / GAME_EXE_NAME
        if exe.exists():
            return exe

    return (
        Path.home()
        / ".local/share/Steam/steamapps/common"
        / GAME_DIR_NAME
        / GAME_EXE_NAME
    )


def resolve_mods_dir(game_exe: Path, mods_dir_arg: str | None) -> Path:
    if mods_dir_arg:
        return expand_path(mods_dir_arg)
    return game_exe.parent / "mods"