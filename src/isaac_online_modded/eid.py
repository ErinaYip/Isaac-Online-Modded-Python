"""Patch External Item Descriptions for online co-op."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .common import (
    EIDNotFoundError,
    PatchError,
    PatchStatus,
    backup_once,
)
from .lua import LuaDocument

EID_ANCHOR = "return listUpdatedForPlayers -- dont evaluate when bad data is present"
EID_MARKER = "-- IsaacOnlineModded: avoid invalid player access after the run ends"
EID_GUARD = (
    EID_MARKER,
    "local stage = Game():GetLevel():GetStage()",
    "if stage == nil or stage >= 13 or stage < 1 then",
    "return listUpdatedForPlayers",
    "end",
)


def find_unique_anchor(lines: list[str]) -> int | None:
    index: int | None = None
    for i, line in enumerate(lines):
        if EID_ANCHOR not in line:
            continue
        if index is not None:
            return None
        index = i
    return index


def matches_block(lines: list[str], index: int, block: Iterable[str]) -> bool:
    block = tuple(block)
    if index + len(block) > len(lines):
        return False
    return all(
        lines[index + offset].strip() == expected
        for offset, expected in enumerate(block)
    )


def matches_return_and_end(lines: list[str], index: int) -> bool:
    return (
        index + 1 < len(lines)
        and lines[index].strip().startswith("return listUpdatedForPlayers")
        and lines[index + 1].strip() == "end"
    )


def matches_legacy_stage_guard(lines: list[str], index: int) -> bool:
    if index + 7 > len(lines):
        return False
    return (
        lines[index + 1].strip() == "if stage == nil then"
        and lines[index + 2].strip().startswith("return listUpdatedForPlayers")
        and lines[index + 3].strip() == "end"
        and "stage >= 13" in lines[index + 4]
        and "stage < 1" in lines[index + 4]
        and matches_return_and_end(lines, index + 5)
    )


def eid_has_stage_guard(lines: list[str], anchor_index: int) -> bool:
    end = min(len(lines), anchor_index + 14)
    for index in range(anchor_index + 1, end):
        if matches_block(lines, index, EID_GUARD):
            return True

        line = lines[index].strip()
        if (
            line == "local stage = Game():GetLevel():GetStage()"
            and matches_legacy_stage_guard(lines, index)
        ):
            return True
        if (
            "Game():GetLevel():GetStage() >= LevelStage.Home" in line
            and matches_return_and_end(lines, index + 1)
        ):
            return True
    return False


def eid_api_status(eid_api: Path) -> PatchStatus:
    document = LuaDocument.read(eid_api)
    anchor_index = find_unique_anchor(document.lines)
    if anchor_index is None:
        return PatchStatus.UNSUPPORTED
    if eid_has_stage_guard(document.lines, anchor_index):
        return PatchStatus.PATCHED
    return PatchStatus.NOT_PATCHED


def patch_eid_api_lua(eid_api: Path, suffix: str, dry_run: bool) -> bool:
    document = LuaDocument.read(eid_api)
    anchor_index = find_unique_anchor(document.lines)
    if anchor_index is None:
        raise PatchError(
            f"The installed EID version is missing a unique patch location: {eid_api}"
        )
    if eid_has_stage_guard(document.lines, anchor_index):
        print(f"Already patched: {eid_api}")
        return False

    block_end: int | None = None
    for index in range(anchor_index + 1, min(len(document.lines), anchor_index + 4)):
        if document.lines[index].strip() == "end":
            block_end = index
            break
    if block_end is None:
        raise PatchError(f"Could not locate the EID player validation block: {eid_api}")

    document.lines[block_end + 1 : block_end + 1] = [
        "",
        "\t\t" + EID_GUARD[0],
        "\t\t" + EID_GUARD[1],
        "\t\t" + EID_GUARD[2],
        "\t\t\t" + EID_GUARD[3],
        "\t\t" + EID_GUARD[4],
    ]

    backup_once(eid_api, suffix, dry_run)
    if dry_run:
        print(f"Would patch: {eid_api}")
    else:
        document.write()
        print(f"Patched: {eid_api}")
    return True


def find_eid_dir(mods_dir: Path) -> Path:
    if not mods_dir.exists():
        raise EIDNotFoundError(f"Mods directory not found: {mods_dir}")
    if not mods_dir.is_dir():
        raise PatchError(f"Mods path is not a directory: {mods_dir}")

    matches = [
        path
        for path in mods_dir.iterdir()
        if path.is_dir()
        and "external" in path.name.lower()
        and "item" in path.name.lower()
        and "descriptions" in path.name.lower()
        and (path / "features" / "eid_api.lua").exists()
    ]
    if not matches:
        raise EIDNotFoundError(f"External Item Descriptions not found in: {mods_dir}")
    return sorted(matches)[0]


def patch_external_item_descriptions(eid_dir: Path, suffix: str, dry_run: bool) -> bool:
    print(f"Using EID mod directory: {eid_dir}")
    eid_api = eid_dir / "features" / "eid_api.lua"
    if not eid_api.exists():
        raise PatchError(f"Required EID file not found: {eid_api}")

    changed = patch_eid_api_lua(eid_api, suffix, dry_run)
    if not changed:
        print("External Item Descriptions already patched.")
    return changed
