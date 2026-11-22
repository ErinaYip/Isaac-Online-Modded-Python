"""Patch Antibirth Music+++ so its music RNG cannot desync online co-op."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .common import (
    AntibirthMusicNotFoundError,
    PatchError,
    PatchStatus,
    backup_once,
)
from .lua import LuaDocument

ANTIBIRTH_MOD_MARKER = 'RegisterMod("Antibirth Music+++"'
ANTIBIRTH_PATCH_MARKER = "-- IsaacOnlineModded: Random() advances the synced RNG"
ANTIBIRTH_FIXED_SEED = (
    "randomRNG:SetSeed((Isaac.GetTime() // 2) + 1, RECOMMENDED_SHIFT_IDX)"
)
ANTIBIRTH_OLD_SEEDS = (
    "randomRNG:SetSeed((Random() // 2) + 1, RECOMMENDED_SHIFT_IDX)",
    # Old replacement file from the upstream repository
    "randomRNG:SetSeed((Game():GetFrameCount() // 2) + 1, RECOMMENDED_SHIFT_IDX)",
)
ANTIBIRTH_UNUSED_SEED = (
    "local seed = Random()",
    "if seed < 1 or seed > 4294967295 then",
    "seed = 256",
    "end",
)


def indent_of(line: str) -> str:
    return line[: len(line) - len(line.lstrip())]


def antibirth_main_path(mod_dir: Path) -> Path:
    return mod_dir / "main.lua"


def is_antibirth_music(mod_dir: Path) -> bool:
    path = antibirth_main_path(mod_dir)
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    return ANTIBIRTH_MOD_MARKER in text


def antibirth_calls_random(lines: Iterable[str]) -> bool:
    return any("Random()" in line.split("--")[0] for line in lines)


def apply_antibirth_fix(lines: list[str]) -> None:
    index = 0
    while index < len(lines):
        line = lines[index]
        indent = indent_of(line)
        if line.strip() in ANTIBIRTH_OLD_SEEDS:
            lines[index] = indent + ANTIBIRTH_FIXED_SEED
            lines.insert(index + 1, indent + ANTIBIRTH_PATCH_MARKER)
            index += 2
            continue

        unused_end = index + len(ANTIBIRTH_UNUSED_SEED)
        unused = [line.strip() for line in lines[index:unused_end]]

        if unused == list(ANTIBIRTH_UNUSED_SEED):
            del lines[index:unused_end]
            lines.insert(index, indent + ANTIBIRTH_PATCH_MARKER)
            index += 1
            continue
        index += 1


def antibirth_music_status(mod_dir: Path) -> PatchStatus:
    lines = LuaDocument.read(antibirth_main_path(mod_dir)).lines
    if not antibirth_calls_random(lines):
        return PatchStatus.PATCHED
    patched_lines = list(lines)
    apply_antibirth_fix(patched_lines)
    if antibirth_calls_random(patched_lines):
        return PatchStatus.UNSUPPORTED
    return PatchStatus.NOT_PATCHED


def patch_antibirth_music(mod_dir: Path, suffix: str, dry_run: bool) -> bool:
    path = antibirth_main_path(mod_dir)
    document = LuaDocument.read(path)
    if not antibirth_calls_random(document.lines):
        print(f"Already patched: {path}")
        return False

    apply_antibirth_fix(document.lines)
    if antibirth_calls_random(document.lines):
        raise PatchError(
            "The installed Antibirth Music+++ version calls Random() in an unknown place."
        )

    backup_once(path, suffix, dry_run)
    if dry_run:
        print(f"Would patch: {path}")
    else:
        document.write()
        print(f"Patched: {path}")
    return True


def find_antibirth_music_dir(mods_dir: Path) -> Path:
    if not mods_dir.exists():
        raise AntibirthMusicNotFoundError(f"Mods directory not found: {mods_dir}")
    if not mods_dir.is_dir():
        raise PatchError(f"Mods path is not a directory: {mods_dir}")

    matches = [
        path
        for path in mods_dir.iterdir()
        if path.is_dir()
        and "antibirth" in path.name.lower()
        and is_antibirth_music(path)
    ]
    if not matches:
        raise AntibirthMusicNotFoundError(
            f"Antibirth Music+++ not found in: {mods_dir}"
        )
    return sorted(matches)[0]
