# Isaac Online Modded Linux

[English](README.md) | [简体中文](README.zh-CN.md)

这是 [xADDBx/Isaac-Online-Modded](https://github.com/xADDBx/Isaac-Online-Modded)
的 Linux/uv 修改版。

本分支去掉了原项目的 Windows UI，并将 patcher 改写为 Python CLI。目标是在
Linux，尤其是 Steam/Proton 环境下，为 **The Binding of Isaac: Rebirth /
Repentance+** 提供可直接运行的补丁工具。

## 功能

- patch `isaac-ng.exe`，允许开启 mod 时进入在线联机，并停止上传 desync
  分析数据。
- 可选 patch `isaac-ng.exe`，让 mod 角色可以在在线联机中选择（需要先应用
  联机 mod 补丁）。
- 安装 Repentance+ Lua runtime shim 到 `resources/scripts/main.lua`，让 Lua mod
  可以使用 `RegisterMod`、`Game()` 和 callbacks 等 API。
- patch **External Item Descriptions**，使其能在在线联机中工作，同时应用让
  在线地图按键能被 Lua mod 收到的游戏补丁。
- patch **Antibirth Music+++**，避免其音乐 RNG 让没有安装该 mod 的玩家 desync。
- 使用纯 uv 管理、运行和构建。

## 使用

```bash
# 在源码目录中使用 uv 运行
uv run isaac-online-modded

# 自动检测不够时，手动指定游戏目录
uv run isaac-online-modded --game-dir "$HOME/.local/share/Steam/steamapps/common/The Binding of Isaac Rebirth"
```

默认 Steam 路径：

```text
$HOME/.local/share/Steam/steamapps/common/The Binding of Isaac Rebirth/isaac-ng.exe
```

默认运行会 patch 游戏可执行文件、安装 Lua runtime，并 patch 已安装的 EID /
Antibirth Music+++。联机角色补丁需要显式开启。

常用命令：

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

`--all` 会 patch 游戏可执行文件（包括联机角色）、安装 Lua runtime、patch EID
（必须已安装），并在已安装时 patch Antibirth Music+++。可以用 `--no-eid`、
`--no-antibirth-music` 或 `--no-lua-runtime` 跳过默认运行中的可选部分。

`--experimental-lua-api` 会额外启用实验性的 Repentance+ Lua API 补丁。它默认
关闭，因为该补丁可能导致游戏无法启动；`--revert-experimental-lua-api` 只撤销
该补丁。

操作日志带有 `[INFO]`、`[WARN]`、`[ERROR]` 前缀，错误输出到 stderr。
`--status` 与 `--print-path` 保持纯数据输出，方便脚本解析。

写入前会自动创建备份，例如 `isaac-ng.exe.bak`、`main.lua.bak` 和
`eid_api.lua.bak`。写入是原子操作，即使运行中断也不会留下被截断的可执行文件。

## 开发

```bash
uv sync
uv run python -m unittest discover -s tests -v
uv lock --check
uv build
```

项目结构：

| 模块 | 作用 |
| --- | --- |
| `cli.py` | 参数解析与流程编排 |
| `common.py` | 补丁模型、状态判断、原子写入、备份 |
| `locator.py` | Steam/库目录与游戏可执行文件定位 |
| `game.py` | `isaac-ng.exe` 二进制补丁 |
| `runtime.py` | Repentance+ Lua runtime shim |
| `lua.py` | 保留 BOM/换行风格的 Lua 文档 |
| `eid.py` | External Item Descriptions 补丁 |
| `antibirth.py` | Antibirth Music+++ 补丁 |
| `status.py` | `--status` 报告 |