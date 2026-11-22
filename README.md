# Isaac Online Modded Linux

[English](README.md) | [简体中文](README.zh-CN.md)

A small Linux/uv version of
[xADDBx/Isaac-Online-Modded](https://github.com/xADDBx/Isaac-Online-Modded).

This fork removes the Windows UI and rewrites the patcher as a Python CLI. It is
intended for **The Binding of Isaac: Rebirth / Repentance+** on Linux,
especially Steam/Proton installs.

## What it does

- Patches `isaac-ng.exe` so online co-op can be entered with mods enabled, and
  stops the desync analytics upload.
- Optionally patches `isaac-ng.exe` so modded characters are selectable in
  online co-op (requires the co-op mods patch).
- Installs the Repentance+ Lua runtime shim at `resources/scripts/main.lua` so
  Lua mods can access APIs such as `RegisterMod`, `Game()`, and callbacks.
- Patches **External Item Descriptions** for online co-op, including the game
  patch that lets the online map button reach Lua mods.
- Patches **Antibirth Music+++** so its music RNG does not desync players
  without the mod.
- Uses pure uv for environment management, running, and builds.

## Usage

```bash
# Run from the source tree with uv
uv run isaac-online-modded

# Specify the game directory if auto-detection is not enough
uv run isaac-online-modded --game-dir "$HOME/.local/share/Steam/steamapps/common/The Binding of Isaac Rebirth"
```

Default Steam path:

```text
$HOME/.local/share/Steam/steamapps/common/The Binding of Isaac Rebirth/isaac-ng.exe
```

The default run patches the game executable, installs the Lua runtime, and
patches any installed EID / Antibirth Music+++ mods. The co-op character patch
is opt-in.

Useful commands:

```bash
uv run isaac-online-modded --status
uv run isaac-online-modded --dry-run
uv run isaac-online-modded --all
uv run isaac-online-modded --patch-game
uv run isaac-online-modded --patch-coop-characters
uv run isaac-online-modded --patch-lua-runtime
uv run isaac-online-modded --patch-eid
uv run isaac-online-modded --patch-antibirth-music
uv run isaac-online-modded --restore
```

`--all` patches the game executable (including the co-op characters), installs
the Lua runtime, patches EID (required to be installed), and patches
Antibirth Music+++ when it is installed. Use `--no-eid`,
`--no-antibirth-music`, or `--no-lua-runtime` to skip optional parts of the
default run.

`--experimental-lua-api` additionally enables the experimental Repentance+ Lua
API patch. It is disabled by default because it can prevent the game from
starting; `--revert-experimental-lua-api` removes only that patch.

Backups are created before writing, for example `isaac-ng.exe.bak`,
`main.lua.bak`, and `eid_api.lua.bak`. Writes are atomic, so an interrupted run
cannot leave a truncated executable.

## Development

```bash
uv sync
uv run python -m unittest discover -s tests -v
uv lock --check
uv build
```

Project layout:

| Module | Purpose |
| --- | --- |
| `cli.py` | Argument parsing and orchestration |
| `common.py` | Patch model, status helpers, atomic writes, backups |
| `locator.py` | Steam/library and game executable discovery |
| `game.py` | `isaac-ng.exe` binary patches |
| `runtime.py` | Repentance+ Lua runtime shim |
| `lua.py` | BOM/newline preserving Lua document |
| `eid.py` | External Item Descriptions patches |
| `antibirth.py` | Antibirth Music+++ patch |
| `status.py` | `--status` report |