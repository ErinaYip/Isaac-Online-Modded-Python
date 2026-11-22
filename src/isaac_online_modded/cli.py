"""Command line entry point for the Isaac Online Modded Python patcher."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .antibirth import (
    ANTIBIRTH_FIXED_SEED,
    ANTIBIRTH_PATCH_MARKER,
    find_antibirth_music_dir,
    patch_antibirth_music,
)
from .common import (
    AntibirthMusicNotFoundError,
    BinaryPatch,
    DEFAULT_BACKUP_SUFFIX,
    EIDNotFoundError,
    ModNotFoundError,
    PatchError,
    PatchStatus,
    STATUS_LABELS,
    apply_binary_patch,
    backup_once,
    binary_patch_status,
    combine_status,
    error,
    grouped_patch_status,
    info,
    restore_backup,
    warn,
    write_file_atomic,
)
from .eid import (
    EID_ANCHOR,
    EID_MARKER,
    eid_api_status,
    eid_has_stage_guard,
    find_eid_dir,
    patch_external_item_descriptions,
)
from .game import (
    ANALYTICS_PATCH,
    BINARY_PATCHES,
    COOP_CHARACTERS_PATCHES,
    COOP_MODS_PATCH,
    EXPERIMENTAL_LUA_API_PATCH,
    MAP_INPUT_PATCHES,
    patch_game_executable,
    revert_binary_patch,
)
from .locator import (
    GAME_DIR_NAME,
    GAME_EXE_NAME,
    candidate_game_dirs,
    detect_game_exe,
    resolve_mods_dir,
)
from .lua import LuaDocument
from .runtime import (
    LUA_RUNTIME_RESOURCE,
    bundled_lua_runtime,
    lua_runtime_is_usable,
    lua_runtime_status,
    patch_lua_runtime,
)
from .status import print_status

__all__ = [
    "ANALYTICS_PATCH",
    "ANTIBIRTH_FIXED_SEED",
    "ANTIBIRTH_PATCH_MARKER",
    "AntibirthMusicNotFoundError",
    "BINARY_PATCHES",
    "BinaryPatch",
    "COOP_CHARACTERS_PATCHES",
    "COOP_MODS_PATCH",
    "DEFAULT_BACKUP_SUFFIX",
    "EIDNotFoundError",
    "EID_ANCHOR",
    "EID_MARKER",
    "EXPERIMENTAL_LUA_API_PATCH",
    "GAME_DIR_NAME",
    "GAME_EXE_NAME",
    "LUA_RUNTIME_RESOURCE",
    "LuaDocument",
    "MAP_INPUT_PATCHES",
    "ModNotFoundError",
    "PatchError",
    "PatchStatus",
    "STATUS_LABELS",
    "apply_binary_patch",
    "backup_once",
    "binary_patch_status",
    "bundled_lua_runtime",
    "candidate_game_dirs",
    "combine_status",
    "detect_game_exe",
    "eid_api_status",
    "eid_has_stage_guard",
    "error",
    "find_antibirth_music_dir",
    "find_eid_dir",
    "grouped_patch_status",
    "info",
    "lua_runtime_is_usable",
    "lua_runtime_status",
    "main",
    "main_entry",
    "parse_args",
    "patch_antibirth_music",
    "patch_external_item_descriptions",
    "patch_game_executable",
    "patch_lua_runtime",
    "print_status",
    "resolve_mods_dir",
    "restore_backup",
    "revert_binary_patch",
    "warn",
    "write_file_atomic",
]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Patch The Binding of Isaac: Rebirth to allow mods in online co-op "
            "on Linux."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "path",
        nargs="?",
        help=(
            "Optional game executable or game directory. Directories are "
            f"resolved to {GAME_EXE_NAME}."
        ),
    )
    parser.add_argument("--game-exe", help=f"Path to {GAME_EXE_NAME}.")
    parser.add_argument("--game-dir", help=f"Path to '{GAME_DIR_NAME}'.")
    parser.add_argument(
        "--mods-dir",
        help="Path to the Isaac mods directory for EID/Antibirth Music+++ auto-patching.",
    )
    parser.add_argument(
        "--patch-game", action="store_true", help="Patch the game executable."
    )
    parser.add_argument(
        "--patch-coop-characters",
        action="store_true",
        help=(
            "Patch the game so modded characters can be selected in online co-op. "
            "Requires the co-op mods patch."
        ),
    )
    parser.add_argument(
        "--patch-lua-runtime",
        action="store_true",
        help=(
            "Install resources/scripts/main.lua so RegisterMod/Game/_RunCallback "
            "exist for Lua mods."
        ),
    )
    parser.add_argument(
        "--patch-eid",
        action="store_true",
        help=(
            "Patch External Item Descriptions for co-op (including the online map "
            "button fix)."
        ),
    )
    parser.add_argument(
        "--patch-antibirth-music",
        action="store_true",
        help="Patch Antibirth Music+++ so its music RNG does not desync online co-op.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help=(
            "Patch the game executable (including co-op characters), Lua runtime, "
            "EID, and the installed Antibirth Music+++."
        ),
    )
    parser.add_argument(
        "--no-eid",
        action="store_true",
        help="Do not auto-patch External Item Descriptions in the default mode.",
    )
    parser.add_argument(
        "--no-antibirth-music",
        action="store_true",
        help="Do not auto-patch Antibirth Music+++ in the default mode.",
    )
    parser.add_argument(
        "--no-lua-runtime",
        action="store_true",
        help="Do not auto-install resources/scripts/main.lua in default/--all mode.",
    )
    parser.add_argument(
        "--experimental-lua-api",
        action="store_true",
        help=(
            "Also apply the experimental Repentance+ Lua API patch. "
            "This is disabled by default because the current candidate patch can "
            "prevent the game from starting."
        ),
    )
    parser.add_argument(
        "--revert-experimental-lua-api",
        action="store_true",
        help=(
            "Revert only the experimental Lua API patch without restoring the "
            "whole executable backup."
        ),
    )
    parser.add_argument(
        "--restore",
        action="store_true",
        help="Restore the game executable from its backup and exit.",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Print the patch status of the game and installed mods, then exit.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without writing files.",
    )
    parser.add_argument(
        "--print-path",
        action="store_true",
        help="Print the detected game executable path and exit.",
    )
    parser.add_argument(
        "--backup-suffix",
        default=DEFAULT_BACKUP_SUFFIX,
        help="Suffix used for backup files.",
    )
    args = parser.parse_args(argv)

    patch_actions = (
        args.patch_game
        or args.patch_coop_characters
        or args.patch_lua_runtime
        or args.patch_eid
        or args.patch_antibirth_music
        or args.all
    )

    explicit_path_options = sum(
        bool(v) for v in (args.path, args.game_exe, args.game_dir)
    )
    if explicit_path_options > 1:
        parser.error("Use only one of positional path, --game-exe, or --game-dir.")
    if args.restore and (patch_actions or args.revert_experimental_lua_api):
        parser.error("--restore cannot be combined with patch actions.")
    if args.revert_experimental_lua_api and patch_actions:
        parser.error(
            "--revert-experimental-lua-api cannot be combined with patch actions."
        )
    if args.status and (
        patch_actions or args.restore or args.revert_experimental_lua_api
    ):
        parser.error("--status cannot be combined with patch actions.")
    if args.no_eid and (args.patch_eid or args.all):
        parser.error("--no-eid cannot be combined with --patch-eid or --all.")
    if args.no_antibirth_music and args.patch_antibirth_music:
        parser.error(
            "--no-antibirth-music cannot be combined with --patch-antibirth-music."
        )
    if args.no_lua_runtime and (args.patch_lua_runtime or args.all):
        parser.error(
            "--no-lua-runtime cannot be combined with --patch-lua-runtime or --all."
        )

    return args


def resolve_mods(mods_dir: Path, finder, optional: bool, name: str) -> Path | None:
    try:
        return finder(mods_dir)
    except ModNotFoundError as exc:
        if not optional:
            raise
        warn(f"{name} not installed; skipping. {exc}")
        return None


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    game_exe = detect_game_exe(args)
    mods_dir = resolve_mods_dir(game_exe, args.mods_dir)

    if args.print_path:
        print(game_exe)
        return 0

    if args.status:
        return print_status(game_exe, mods_dir)

    if args.restore:
        restore_backup(game_exe, args.backup_suffix, args.dry_run)
        return 0
    if args.revert_experimental_lua_api:
        revert_binary_patch(
            game_exe, EXPERIMENTAL_LUA_API_PATCH, args.backup_suffix, args.dry_run
        )
        return 0

    explicit_action = (
        args.patch_game
        or args.patch_coop_characters
        or args.patch_lua_runtime
        or args.patch_eid
        or args.patch_antibirth_music
        or args.all
    )
    patch_game = args.patch_game or args.all
    patch_coop_characters = args.patch_coop_characters or args.all
    patch_runtime = args.patch_lua_runtime or args.all
    patch_eid = args.patch_eid or args.all
    patch_music = args.patch_antibirth_music or (
        args.all and not args.no_antibirth_music
    )
    eid_optional = False
    music_optional = args.all
    if not explicit_action:
        patch_game = True
        patch_runtime = not args.no_lua_runtime
        patch_eid = not args.no_eid
        patch_music = not args.no_antibirth_music
        eid_optional = patch_eid
        music_optional = True

    eid_dir: Path | None = None
    if patch_eid:
        eid_dir = resolve_mods(
            mods_dir, find_eid_dir, eid_optional, "External Item Descriptions"
        )

    music_dir: Path | None = None
    if patch_music:
        music_dir = resolve_mods(
            mods_dir, find_antibirth_music_dir, music_optional, "Antibirth Music+++"
        )

    exe_patch_selected = (
        patch_game
        or patch_coop_characters
        or eid_dir is not None
        or args.experimental_lua_api
    )
    if exe_patch_selected:
        patch_game_executable(
            game_exe,
            args.backup_suffix,
            args.dry_run,
            patch_coop=patch_game,
            patch_coop_characters=patch_coop_characters,
            patch_map_input=eid_dir is not None,
            patch_experimental_lua_api=args.experimental_lua_api,
        )
    if patch_runtime:
        patch_lua_runtime(game_exe, args.backup_suffix, args.dry_run)
    if eid_dir is not None:
        patch_external_item_descriptions(eid_dir, args.backup_suffix, args.dry_run)
    if music_dir is not None:
        patch_antibirth_music(music_dir, args.backup_suffix, args.dry_run)

    return 0


def main_entry() -> None:
    try:
        raise SystemExit(main(sys.argv[1:]))
    except PatchError as exc:
        error(exc)
        raise SystemExit(1)


if __name__ == "__main__":
    main_entry()
