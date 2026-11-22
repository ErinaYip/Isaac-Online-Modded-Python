"""Human readable patch status report for a game installation."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from .antibirth import antibirth_music_status, find_antibirth_music_dir
from .common import (
    PatchError,
    PatchStatus,
    STATUS_LABELS,
    combine_status,
    error,
)
from .eid import eid_api_status, find_eid_dir
from .game import coop_characters_status, coop_status, map_input_status
from .runtime import lua_runtime_status

STATUS_WIDTH = 30


def status_line(name: str, value: str) -> None:
    print(f"{name + ':':<{STATUS_WIDTH}}{value}")


def print_status(game_exe: Path, mods_dir: Path) -> int:
    if not game_exe.is_file():
        error(f"Game executable not found: {game_exe}")
        return 1

    try:
        body = game_exe.read_bytes()
    except OSError as exc:
        raise PatchError(f"Could not read game executable: {exc}") from exc

    coop = coop_status(body)
    coop_characters = coop_characters_status(body)
    map_input = map_input_status(body)

    status_line("Co-op mods", STATUS_LABELS[coop])
    characters_label = STATUS_LABELS[coop_characters]
    if coop is not PatchStatus.PATCHED and coop_characters is PatchStatus.NOT_PATCHED:
        characters_label += " (requires the co-op mods patch)"
    status_line("Co-op characters", characters_label)
    status_line("Online map input", STATUS_LABELS[map_input])
    status_line("Lua runtime", lua_runtime_status(game_exe))

    eid_dir = optional_mod_dir(find_eid_dir, mods_dir)
    if eid_dir is None:
        status_line("External Item Descriptions", "not installed")
    else:
        try:
            eid_status = combine_status(
                eid_api_status(eid_dir / "features" / "eid_api.lua"), map_input
            )
            label = STATUS_LABELS[eid_status]
        except (OSError, PatchError):
            label = "unavailable"
        status_line("External Item Descriptions", label)

    music_dir = optional_mod_dir(find_antibirth_music_dir, mods_dir)
    if music_dir is None:
        status_line("Antibirth Music+++", "not installed")
    else:
        try:
            label = STATUS_LABELS[antibirth_music_status(music_dir)]
        except (OSError, PatchError):
            label = "unavailable"
        status_line("Antibirth Music+++", label)

    return 0


def optional_mod_dir(finder: Callable[[Path], Path], mods_dir: Path) -> Path | None:
    try:
        return finder(mods_dir)
    except PatchError:
        return None
