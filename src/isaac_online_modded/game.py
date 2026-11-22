"""Binary patches for ``isaac-ng.exe``."""

from __future__ import annotations

from pathlib import Path

from .common import (
    BinaryPatch,
    PatchError,
    PatchStatus,
    apply_binary_patch,
    backup_once,
    binary_patch_status,
    combine_status,
    grouped_patch_status,
    write_file_atomic,
)
from .locator import GAME_EXE_NAME, candidate_game_dirs

COOP_MODS_PATCH = BinaryPatch(
    "online co-op mod gate",
    bytes.fromhex("83E802742A83E801741E83E801741232C08B4DF464890D00000000"),
    bytes.fromhex("83E802909083E801909083E801909032C08B4DF464890D00000000"),
)

ANALYTICS_PATCH = BinaryPatch(
    "desync analytics sender",
    bytes.fromhex("558BEC83EC10535657FF15"),
    bytes.fromhex("C38BEC83EC10535657FF15"),
)

# The co-op character patch lets modded characters be selectable in online
# co-op.  It only works on top of the co-op mod gate patch.
COOP_CHARACTERS_PATCHES = (
    BinaryPatch(
        "co-op character toggle",
        bytes.fromhex(
            "8A4F0984C9510F94C033D284C98847090FB647080F44D303D08D04528D0CC5503BB400E8EF450600"
        ),
        bytes.fromhex(
            "807709010FB647083C117604B001EB180FB657096BD21203D06BCA185181C1503BB400E8EF450600"
        ),
    ),
    BinaryPatch(
        "co-op character cycle",
        bytes.fromhex(
            "8A7F0833F6807F0900B9120000008ADF0F45F10F1F0002D8885F0880FBFF7508C6470811B311EB0B80FB127206C647080032DB0FB6C303C6518D04408D0CC5503BB400E84E45060084C075078B45083ADF75C3817DF8E90300007452"
        ),
        bytes.fromhex(
            "8A7F088ADFBEE0DFC9008B0E2B4EFCC1F90383C1128A450802D83AD97209C0F8078AD822D902D8885F0880FB1273200FB657096BD2120FB6CB03CA6BC9188D8C0E705BEAFF51E84B45060084C074BB807DF8E9745990909090909090"
        ),
    ),
    BinaryPatch(
        "co-op character relocation",
        bytes.fromhex("C83AD33A693B933B033C"),
        bytes.fromhex("C83AD33A303B933B033C"),
    ),
    BinaryPatch(
        "co-op character availability",
        bytes.fromhex(
            "0FB6C1518D04C08D04428D04408D0CC5503BB400E877D0FFFFC3CCCCCCCCCCCC"
        ),
        bytes.fromhex(
            "83FA127203B001C30FB6C16BC01203C26BC8185181C1503BB400E871D0FFFFC3"
        ),
    ),
    BinaryPatch(
        "co-op character availability relocation",
        bytes.fromhex("C400000040305A306330"),
        bytes.fromhex("C400000046305A306330"),
    ),
)

# Online inputs are sent as a 16 bit button mask.  The action -> bit switch
# drops ACTION_MAP, so Lua mods (EID) never see it pressed online.  Turn the
# switch into a plain table lookup and send ACTION_MAP as the unused bit 15.
MAP_INPUT_PATCHES = (
    BinaryPatch(
        "online map input switch",
        bytes.fromhex("83F92277650FB681C0EE9000FF248580EE9000"),
        bytes.fromhex("83F92277650FB681C0EE9000C3248580EE9000"),
    ),
    BinaryPatch(
        "online map input table",
        bytes.fromhex(
            "000102030405060708090A0B0F0F0C0F0F0F0D0F0F0F0F0F0F0F0F0F0F0F0F0F0F0F0E"
        ),
        bytes.fromhex(
            "000102030405060708090A0BFF0F0CFFFFFF0DFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF0E"
        ),
    ),
)

# Linux fork only: this patch is disabled by default because a candidate patch
# for the current game version can prevent the game from starting.
EXPERIMENTAL_LUA_API_PATCH = BinaryPatch(
    "Lua mod API in Repentance+",
    bytes.fromhex("8A45088BCE88461CE80C6300006854EDB600"),
    bytes.fromhex("B001908BCE88461CE80C6300006854EDB600"),
)

# Compatibility aliases kept for callers of the previous CLI surface.
BINARY_PATCHES = (COOP_MODS_PATCH, ANALYTICS_PATCH)


def coop_status(body: bytes | bytearray) -> PatchStatus:
    return combine_status(
        binary_patch_status(body, COOP_MODS_PATCH),
        binary_patch_status(body, ANALYTICS_PATCH),
    )


def coop_characters_status(body: bytes | bytearray) -> PatchStatus:
    return grouped_patch_status(body, COOP_CHARACTERS_PATCHES)


def map_input_status(body: bytes | bytearray) -> PatchStatus:
    return grouped_patch_status(body, MAP_INPUT_PATCHES)


def _patch_group(
    body: bytearray,
    patches: tuple[BinaryPatch, ...],
    title: str,
) -> bool:
    status = grouped_patch_status(body, patches)
    if status is PatchStatus.UNSUPPORTED:
        raise PatchError(f"The {title} does not support this game version.")
    if status is PatchStatus.PATCHED:
        print(f"Already patched: {title}")
        return False

    changed = False
    for patch in patches:
        changed |= apply_binary_patch(body, patch)
    if grouped_patch_status(body, patches) is not PatchStatus.PATCHED:
        raise PatchError(f"The {title} could not be verified.")
    return changed


def patch_game_executable(
    game_exe: Path,
    suffix: str,
    dry_run: bool,
    *,
    patch_coop: bool = False,
    patch_coop_characters: bool = False,
    patch_map_input: bool = False,
    patch_experimental_lua_api: bool = False,
) -> bool:
    if not game_exe.exists():
        searched = "\n  ".join(str(p / GAME_EXE_NAME) for p in candidate_game_dirs())
        raise PatchError(
            f"Game executable not found: {game_exe}\n"
            f"Pass --game-exe/--game-dir, set ISAAC_GAME_EXE/ISAAC_GAME_DIR, or install Steam in the default path.\n"
            f"Searched candidates:\n  {searched}"
        )
    if not game_exe.is_file():
        raise PatchError(f"Game executable is not a file: {game_exe}")

    original = game_exe.read_bytes()
    body = bytearray(original)
    changed = False

    if patch_coop:
        for patch in (COOP_MODS_PATCH, ANALYTICS_PATCH):
            changed |= apply_binary_patch(body, patch)

    if patch_coop_characters:
        if binary_patch_status(body, COOP_MODS_PATCH) is not PatchStatus.PATCHED:
            raise PatchError(
                "The co-op mods patch must be applied before the co-op character "
                "patch. Run --patch-game first."
            )
        changed |= _patch_group(body, COOP_CHARACTERS_PATCHES, "co-op character patch")

    if patch_map_input:
        changed |= _patch_group(body, MAP_INPUT_PATCHES, "online map button fix")

    if patch_experimental_lua_api:
        changed |= apply_binary_patch(body, EXPERIMENTAL_LUA_API_PATCH)

    if not changed:
        print("Game executable already patched.")
        return False

    backup_once(game_exe, suffix, dry_run)
    if dry_run:
        print(f"Would write patched executable: {game_exe}")
    else:
        write_file_atomic(game_exe, bytes(body))
        print(f"Patched executable: {game_exe}")
    return True


def revert_binary_patch(
    game_exe: Path, patch: BinaryPatch, suffix: str, dry_run: bool
) -> bool:
    if not game_exe.exists():
        raise PatchError(f"Game executable not found: {game_exe}")
    if not game_exe.is_file():
        raise PatchError(f"Game executable is not a file: {game_exe}")

    body = bytearray(game_exe.read_bytes())
    patched_count = body.count(patch.patched)
    original_count = body.count(patch.original)

    if patched_count == 0:
        if original_count:
            print(f"Not applied: {patch.name}; original bytes already present.")
            return False
        raise PatchError(
            f"Neither patched nor original pattern for {patch.name!r} was found."
        )
    if patched_count != 1:
        raise PatchError(
            f"Expected exactly one patched pattern for {patch.name!r}, found {patched_count}."
        )

    index = body.find(patch.patched)
    print(f"Will revert {patch.name} at offset 0x{index:x}")
    backup_once(game_exe, suffix, dry_run)
    if dry_run:
        print(f"Would write reverted executable: {game_exe}")
    else:
        body[index : index + len(patch.original)] = patch.original
        write_file_atomic(game_exe, bytes(body))
        print(f"Reverted {patch.name}: {game_exe}")
    return True
