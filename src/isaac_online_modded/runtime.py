"""Install the bundled Repentance+ Lua runtime shim."""

from __future__ import annotations

import importlib.resources
from pathlib import Path

from .common import PatchError, backup_once, write_file_atomic


LUA_RUNTIME_RESOURCE = "repentance_plus_main.lua"


def bundled_lua_runtime() -> str:
    return (
        importlib.resources.files("isaac_online_modded")
        .joinpath("resources", LUA_RUNTIME_RESOURCE)
        .read_text(encoding="utf-8")
    )


def lua_runtime_is_usable(text: str) -> bool:
    return (
        "function RegisterMod" in text
        and "Game = Game_0" in text
        and "function _RunCallback" in text
    )


def lua_runtime_status(game_exe: Path) -> str:
    target = game_exe.parent / "resources" / "scripts" / "main.lua"
    if not target.exists():
        return "not installed"
    text = target.read_text(encoding="utf-8", errors="replace")
    if text == bundled_lua_runtime():
        return "installed"
    if lua_runtime_is_usable(text):
        return "installed (modified)"
    return "incomplete"


def patch_lua_runtime(game_exe: Path, suffix: str, dry_run: bool) -> bool:
    scripts_dir = game_exe.parent / "resources" / "scripts"
    if not scripts_dir.exists():
        raise PatchError(f"Lua scripts directory not found: {scripts_dir}")
    if not scripts_dir.is_dir():
        raise PatchError(f"Lua scripts path is not a directory: {scripts_dir}")

    target = scripts_dir / "main.lua"
    runtime = bundled_lua_runtime()
    if not lua_runtime_is_usable(runtime):
        raise PatchError(f"Bundled Lua runtime is incomplete: {LUA_RUNTIME_RESOURCE}")

    if target.exists():
        current = target.read_text(encoding="utf-8", errors="replace")
        if current == runtime:
            print(f"Lua runtime already installed: {target}")
            return False
        if lua_runtime_is_usable(current):
            print(f"Existing Lua runtime looks usable; leaving unchanged: {target}")
            return False
        backup_once(target, suffix, dry_run)
        if dry_run:
            print(f"Would replace incomplete Lua runtime: {target}")
        else:
            write_file_atomic(target, runtime.encode("utf-8"))
            print(f"Replaced incomplete Lua runtime: {target}")
        return True

    if dry_run:
        print(f"Would install Lua runtime: {target}")
    else:
        write_file_atomic(target, runtime.encode("utf-8"))
        print(f"Installed Lua runtime: {target}")
    return True