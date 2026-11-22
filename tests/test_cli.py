from __future__ import annotations

import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from isaac_online_modded import cli, common

EID_API_CONTENT = (
    "local function demo()\n"
    "  return listUpdatedForPlayers -- dont evaluate when bad data is present\n"
    "  player:HasCollectible(1)\n"
    "end\n"
)

EID_MAIN_CONTENT = (
    "EID = {}\n"
    "EID.isMultiplayer = false -- Used to color P1's highlight/outline indicators (single player just uses white)\n"
    "EID.isMultiplayer = false\n"
)

MUSIC_MAIN_CONTENT = (
    'local abm3p = RegisterMod("Antibirth Music+++", 1)\n'
    "local RECOMMENDED_SHIFT_IDX = 35\n"
    "local randomRNG = RNG()\n"
    "randomRNG:SetSeed((Random() // 2) + 1, RECOMMENDED_SHIFT_IDX)\n"
    "\n"
    "local function updateRandomAltMusic()\n"
    "  local rng = RNG()\n"
    "  if condition then\n"
    "    rng:SetSeed(1, RECOMMENDED_SHIFT_IDX)\n"
    "  else\n"
    "    local seed = Random()\n"
    "    if seed < 1 or seed > 4294967295 then\n"
    "      seed = 256\n"
    "    end\n"
    "    rng:SetSeed(randomRNG:RandomInt(4294967295) + 1, RECOMMENDED_SHIFT_IDX)\n"
    "  end\n"
    "end\n"
)

GAME_PATCHES = (
    cli.COOP_MODS_PATCH,
    cli.ANALYTICS_PATCH,
    *cli.COOP_CHARACTERS_PATCHES,
    *cli.MAP_INPUT_PATCHES,
)


def executable_bytes(
    *, include_experimental_lua_api: bool = False, patched: bool = False
) -> bytes:
    patches = list(GAME_PATCHES)
    if include_experimental_lua_api:
        patches.append(cli.EXPERIMENTAL_LUA_API_PATCH)
    chunks = [patch.patched if patched else patch.original for patch in patches]
    return b"HEAD" + b"SEP".join(chunks) + b"TAIL"


def make_game_tree(
    root: Path,
    *,
    include_experimental_lua_api: bool = False,
    with_eid: bool = True,
    with_music: bool = False,
) -> Path:
    game_dir = root / "The Binding of Isaac Rebirth"
    (game_dir / "resources" / "scripts").mkdir(parents=True)
    (game_dir / cli.GAME_EXE_NAME).write_bytes(
        executable_bytes(include_experimental_lua_api=include_experimental_lua_api)
    )

    if with_eid:
        eid_dir = game_dir / "mods" / "External Item Descriptions"
        (eid_dir / "features").mkdir(parents=True)
        (eid_dir / "main.lua").write_text(EID_MAIN_CONTENT, encoding="utf-8")
        (eid_dir / "features" / "eid_api.lua").write_text(
            EID_API_CONTENT, encoding="utf-8"
        )

    if with_music:
        music_dir = game_dir / "mods" / "Antibirth Music+++"
        music_dir.mkdir(parents=True)
        (music_dir / "main.lua").write_text(MUSIC_MAIN_CONTENT, encoding="utf-8")

    return game_dir


def run(argv: list[str]) -> tuple[int, str]:
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        code = cli.main(argv)
    return code, output.getvalue()


def assert_status(output: str, name: str, value: str) -> None:
    prefix = f"{name}:"
    for line in output.splitlines():
        if line.startswith(prefix):
            assert value in line, f"{name!r} line does not contain {value!r}: {line!r}"
            return
    raise AssertionError(f"missing status line {name!r} in:\n{output}")


def eid_api_path(game_dir: Path) -> Path:
    return game_dir / "mods" / "External Item Descriptions" / "features" / "eid_api.lua"


def music_main_path(game_dir: Path) -> Path:
    return game_dir / "mods" / "Antibirth Music+++" / "main.lua"


class LogFormatTest(unittest.TestCase):
    def test_no_color_for_non_tty(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            common.info("hello")
        self.assertEqual(output.getvalue(), "[INFO] hello\n")

    def test_force_color_adds_ansi(self) -> None:
        output = io.StringIO()
        with mock.patch.dict(os.environ, {"FORCE_COLOR": "1"}, clear=False):
            with contextlib.redirect_stdout(output):
                common.warn("careful")
        self.assertIn("\x1b[33m[WARN]\x1b[0m", output.getvalue())

    def test_no_color_wins_over_force_color(self) -> None:
        output = io.StringIO()
        environment = {"FORCE_COLOR": "1", "NO_COLOR": "1"}
        with mock.patch.dict(os.environ, environment, clear=False):
            with contextlib.redirect_stdout(output):
                common.info("plain")
        self.assertEqual(output.getvalue(), "[INFO] plain\n")


class BinaryPatchTest(unittest.TestCase):
    def test_patch_regions_have_equal_length(self) -> None:
        for patch in (*GAME_PATCHES, cli.EXPERIMENTAL_LUA_API_PATCH):
            self.assertEqual(len(patch.original), len(patch.patched), patch.name)

    def test_ambiguous_pattern_is_unsupported(self) -> None:
        patch = cli.COOP_MODS_PATCH
        body = patch.original + patch.original
        self.assertIs(cli.binary_patch_status(body, patch), cli.PatchStatus.UNSUPPORTED)


class CLITest(unittest.TestCase):
    def test_default_patches_game_runtime_eid_and_music(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = make_game_tree(
                Path(tmp),
                include_experimental_lua_api=True,
                with_eid=True,
                with_music=True,
            )
            exe = game_dir / cli.GAME_EXE_NAME
            original = exe.read_bytes()

            code, output = run(["--game-exe", str(exe)])
            self.assertEqual(code, 0)
            self.assertIn("Will patch online map input switch", output)

            patched = exe.read_bytes()
            self.assertNotEqual(patched, original)
            for patch in (cli.COOP_MODS_PATCH, cli.ANALYTICS_PATCH):
                self.assertIn(patch.patched, patched)
            for patch in cli.MAP_INPUT_PATCHES:
                self.assertIn(patch.patched, patched)
            # The co-op character patch is opt-in and stays untouched.
            for patch in cli.COOP_CHARACTERS_PATCHES:
                self.assertIn(patch.original, patched)
            # The experimental Lua API patch is opt-in.
            self.assertIn(cli.EXPERIMENTAL_LUA_API_PATCH.original, patched)

            self.assertEqual(
                (game_dir / f"{cli.GAME_EXE_NAME}.bak").read_bytes(), original
            )

            runtime_text = (game_dir / "resources" / "scripts" / "main.lua").read_text(
                encoding="utf-8"
            )
            self.assertIn("function RegisterMod", runtime_text)
            self.assertIn("Game = Game_0", runtime_text)

            eid_api = eid_api_path(game_dir)
            eid_text = eid_api.read_text(encoding="utf-8")
            self.assertIn(cli.EID_MARKER, eid_text)
            self.assertIn("if stage == nil or stage >= 13 or stage < 1 then", eid_text)
            self.assertTrue((eid_api.with_name("eid_api.lua.bak")).exists())
            # EID main.lua is no longer patched.
            main_lua = game_dir / "mods" / "External Item Descriptions" / "main.lua"
            self.assertIn(
                "EID.isMultiplayer = false", main_lua.read_text(encoding="utf-8")
            )

            music_text = music_main_path(game_dir).read_text(encoding="utf-8")
            self.assertIn(cli.ANTIBIRTH_FIXED_SEED, music_text)
            self.assertNotIn("randomRNG:SetSeed((Random() // 2)", music_text)
            self.assertNotIn("local seed = Random()", music_text)
            self.assertIn(cli.ANTIBIRTH_PATCH_MARKER, music_text)

            code, _ = run(["--game-exe", str(exe)])
            self.assertEqual(code, 0)
            self.assertEqual(exe.read_bytes(), patched)

            code, _ = run(["--game-exe", str(exe), "--restore"])
            self.assertEqual(code, 0)
            self.assertEqual(exe.read_bytes(), original)

    def test_default_skips_mods_that_are_not_installed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = make_game_tree(Path(tmp), with_eid=False, with_music=False)
            exe = game_dir / cli.GAME_EXE_NAME

            code, output = run(["--game-exe", str(exe)])
            self.assertEqual(code, 0)
            self.assertIn("External Item Descriptions not installed", output)
            self.assertIn("Antibirth Music+++ not installed", output)
            for patch in (cli.COOP_MODS_PATCH, cli.ANALYTICS_PATCH):
                self.assertIn(patch.patched, exe.read_bytes())
            for patch in cli.MAP_INPUT_PATCHES:
                self.assertIn(patch.original, exe.read_bytes())
            self.assertTrue((game_dir / "resources" / "scripts" / "main.lua").exists())

    def test_all_patches_coop_characters(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = make_game_tree(Path(tmp))
            exe = game_dir / cli.GAME_EXE_NAME

            code, _ = run(["--game-exe", str(exe), "--all"])
            self.assertEqual(code, 0)
            patched = exe.read_bytes()
            for patch in cli.COOP_CHARACTERS_PATCHES:
                self.assertIn(patch.patched, patched)
            for patch in cli.MAP_INPUT_PATCHES:
                self.assertIn(patch.patched, patched)

    def test_all_patches_antibirth_music_when_installed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = make_game_tree(Path(tmp), with_music=True)
            exe = game_dir / cli.GAME_EXE_NAME

            code, _ = run(["--game-exe", str(exe), "--all"])
            self.assertEqual(code, 0)
            text = music_main_path(game_dir).read_text(encoding="utf-8")
            self.assertIn(cli.ANTIBIRTH_FIXED_SEED, text)

    def test_no_antibirth_music_skips_default_patch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = make_game_tree(Path(tmp), with_music=True)
            exe = game_dir / cli.GAME_EXE_NAME
            music_main = music_main_path(game_dir)
            before = music_main.read_text(encoding="utf-8")

            code, _ = run(["--game-exe", str(exe), "--no-antibirth-music"])
            self.assertEqual(code, 0)
            self.assertEqual(music_main.read_text(encoding="utf-8"), before)
            self.assertFalse(music_main.with_name("main.lua.bak").exists())

    def test_patch_coop_characters_requires_coop_patch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = make_game_tree(Path(tmp))
            exe = game_dir / cli.GAME_EXE_NAME

            with self.assertRaisesRegex(cli.PatchError, "co-op mods patch"):
                run(["--game-exe", str(exe), "--patch-coop-characters"])

            code, _ = run(["--game-exe", str(exe), "--patch-game"])
            self.assertEqual(code, 0)
            code, _ = run(["--game-exe", str(exe), "--patch-coop-characters"])
            self.assertEqual(code, 0)
            for patch in cli.COOP_CHARACTERS_PATCHES:
                self.assertIn(patch.patched, exe.read_bytes())

    def test_patch_eid_also_patches_online_map_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = make_game_tree(Path(tmp))
            exe = game_dir / cli.GAME_EXE_NAME

            code, _ = run(["--game-exe", str(exe), "--patch-eid"])
            self.assertEqual(code, 0)
            patched = exe.read_bytes()
            for patch in cli.MAP_INPUT_PATCHES:
                self.assertIn(patch.patched, patched)
            self.assertIn(cli.COOP_MODS_PATCH.original, patched)
            self.assertIn(
                cli.EID_MARKER, eid_api_path(game_dir).read_text(encoding="utf-8")
            )

    def test_explicit_eid_requires_installation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = make_game_tree(Path(tmp), with_eid=False)
            exe = game_dir / cli.GAME_EXE_NAME
            original = exe.read_bytes()

            with self.assertRaises(cli.EIDNotFoundError):
                run(["--game-exe", str(exe), "--patch-eid"])
            self.assertEqual(exe.read_bytes(), original)

            with self.assertRaises(cli.EIDNotFoundError):
                run(["--game-exe", str(exe), "--all"])

    def test_patch_antibirth_music(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = make_game_tree(Path(tmp), with_eid=False, with_music=True)
            exe = game_dir / cli.GAME_EXE_NAME

            code, _ = run(["--game-exe", str(exe), "--patch-antibirth-music"])
            self.assertEqual(code, 0)
            text = music_main_path(game_dir).read_text(encoding="utf-8")
            self.assertIn(cli.ANTIBIRTH_FIXED_SEED, text)
            self.assertNotIn("local seed = Random()", text)
            self.assertTrue(
                (music_main_path(game_dir).with_name("main.lua.bak")).exists()
            )

            code, _ = run(["--game-exe", str(exe), "--patch-antibirth-music"])
            self.assertEqual(code, 0)
            self.assertEqual(
                music_main_path(game_dir).read_text(encoding="utf-8"), text
            )

    def test_explicit_antibirth_music_requires_installation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = make_game_tree(Path(tmp), with_music=False)
            exe = game_dir / cli.GAME_EXE_NAME

            with self.assertRaises(cli.AntibirthMusicNotFoundError):
                run(["--game-exe", str(exe), "--patch-antibirth-music"])

    def test_experimental_lua_api_patch_is_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = make_game_tree(
                Path(tmp), include_experimental_lua_api=True, with_eid=False
            )
            exe = game_dir / cli.GAME_EXE_NAME

            code, _ = run(["--game-exe", str(exe), "--no-eid"])
            self.assertEqual(code, 0)
            data = exe.read_bytes()
            self.assertIn(cli.EXPERIMENTAL_LUA_API_PATCH.original, data)
            self.assertNotIn(cli.EXPERIMENTAL_LUA_API_PATCH.patched, data)

            code, _ = run(
                ["--game-exe", str(exe), "--no-eid", "--experimental-lua-api"]
            )
            self.assertEqual(code, 0)
            data = exe.read_bytes()
            self.assertNotIn(cli.EXPERIMENTAL_LUA_API_PATCH.original, data)
            self.assertIn(cli.EXPERIMENTAL_LUA_API_PATCH.patched, data)

    def test_revert_experimental_lua_api_patch_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = make_game_tree(
                Path(tmp), include_experimental_lua_api=True, with_eid=False
            )
            exe = game_dir / cli.GAME_EXE_NAME

            code, _ = run(
                ["--game-exe", str(exe), "--no-eid", "--experimental-lua-api"]
            )
            self.assertEqual(code, 0)
            self.assertIn(cli.EXPERIMENTAL_LUA_API_PATCH.patched, exe.read_bytes())

            code, _ = run(["--game-exe", str(exe), "--revert-experimental-lua-api"])
            self.assertEqual(code, 0)
            repaired = exe.read_bytes()
            self.assertIn(cli.EXPERIMENTAL_LUA_API_PATCH.original, repaired)
            self.assertNotIn(cli.EXPERIMENTAL_LUA_API_PATCH.patched, repaired)
            for patch in (cli.COOP_MODS_PATCH, cli.ANALYTICS_PATCH):
                self.assertIn(patch.patched, repaired)

    def test_no_eid_patches_game_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = make_game_tree(Path(tmp))
            exe = game_dir / cli.GAME_EXE_NAME

            code, _ = run(["--game-exe", str(exe), "--no-eid"])
            self.assertEqual(code, 0)
            for patch in (cli.COOP_MODS_PATCH, cli.ANALYTICS_PATCH):
                self.assertIn(patch.patched, exe.read_bytes())
            for patch in cli.MAP_INPUT_PATCHES:
                self.assertIn(patch.original, exe.read_bytes())
            self.assertIn(
                "EID.isMultiplayer = false",
                (
                    game_dir / "mods" / "External Item Descriptions" / "main.lua"
                ).read_text(encoding="utf-8"),
            )

    def test_dry_run_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = make_game_tree(Path(tmp), with_eid=True, with_music=True)
            exe = game_dir / cli.GAME_EXE_NAME
            original = exe.read_bytes()
            eid_before = eid_api_path(game_dir).read_bytes()
            music_before = music_main_path(game_dir).read_bytes()

            code, _ = run(["--game-exe", str(exe), "--all", "--dry-run"])
            self.assertEqual(code, 0)
            self.assertEqual(exe.read_bytes(), original)
            self.assertEqual(eid_api_path(game_dir).read_bytes(), eid_before)
            self.assertEqual(music_main_path(game_dir).read_bytes(), music_before)
            self.assertFalse((game_dir / f"{cli.GAME_EXE_NAME}.bak").exists())
            self.assertFalse((game_dir / "resources" / "scripts" / "main.lua").exists())

    def test_status_reports_game_and_mods(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = make_game_tree(Path(tmp), with_eid=True, with_music=True)
            exe = game_dir / cli.GAME_EXE_NAME

            code, output = run(["--game-exe", str(exe), "--status"])
            self.assertEqual(code, 0)
            assert_status(output, "Co-op mods", "not patched")
            assert_status(output, "Co-op characters", "not patched")
            assert_status(output, "Online map input", "not patched")
            assert_status(output, "Lua runtime", "not installed")
            assert_status(output, "External Item Descriptions", "not patched")
            assert_status(output, "Antibirth Music+++", "not patched")

            run(["--game-exe", str(exe), "--all"])
            code, output = run(["--game-exe", str(exe), "--status"])
            self.assertEqual(code, 0)
            assert_status(output, "Co-op mods", "patched")
            assert_status(output, "Co-op characters", "patched")
            assert_status(output, "Online map input", "patched")
            assert_status(output, "Lua runtime", "installed")
            assert_status(output, "External Item Descriptions", "patched")
            assert_status(output, "Antibirth Music+++", "patched")

    def test_game_dir_argument_resolves_executable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = make_game_tree(Path(tmp))
            args = cli.parse_args(["--game-dir", str(game_dir), "--print-path"])
            self.assertEqual(cli.detect_game_exe(args), game_dir / cli.GAME_EXE_NAME)


class EIDPatchTest(unittest.TestCase):
    def test_legacy_stage_guard_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = make_game_tree(Path(tmp))
            eid_api = eid_api_path(game_dir)
            legacy = (
                "local function demo()\n"
                "  return listUpdatedForPlayers -- dont evaluate when bad data is present\n"
                "\t\tlocal stage = Game():GetLevel():GetStage()\n"
                "\t\tif stage == nil then\n"
                "\t\t\treturn listUpdatedForPlayers\n"
                "\t\tend\n"
                "\t\tif EID.isOnlineMultiplayer and (stage >= 13 or stage < 1) then\n"
                "\t\t\treturn listUpdatedForPlayers -- Calling player:HasCollectible can cause a crash\n"
                "\t\tend\n"
                "  player:HasCollectible(1)\n"
                "end\n"
            )
            eid_api.write_text(legacy, encoding="utf-8")

            code, _ = run(
                ["--game-exe", str(game_dir / cli.GAME_EXE_NAME), "--patch-eid"]
            )
            self.assertEqual(code, 0)
            self.assertEqual(eid_api.read_text(encoding="utf-8"), legacy)
            self.assertIs(cli.eid_api_status(eid_api), cli.PatchStatus.PATCHED)

    def test_missing_unique_anchor_is_unsupported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = make_game_tree(Path(tmp))
            eid_api = eid_api_path(game_dir)
            eid_api.write_text(
                cli.EID_ANCHOR + "\n" + cli.EID_ANCHOR + "\n", encoding="utf-8"
            )
            self.assertIs(cli.eid_api_status(eid_api), cli.PatchStatus.UNSUPPORTED)
            with self.assertRaises(cli.PatchError):
                run(["--game-exe", str(game_dir / cli.GAME_EXE_NAME), "--patch-eid"])

    def test_patch_preserves_bom_and_crlf(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            game_dir = make_game_tree(Path(tmp))
            eid_api = eid_api_path(game_dir)
            eid_api.write_bytes(
                b"\xef\xbb\xbf" + EID_API_CONTENT.replace("\n", "\r\n").encode("utf-8")
            )

            code, _ = run(
                ["--game-exe", str(game_dir / cli.GAME_EXE_NAME), "--patch-eid"]
            )
            self.assertEqual(code, 0)
            data = eid_api.read_bytes()
            self.assertTrue(data.startswith(b"\xef\xbb\xbf"))
            self.assertIn(b"\r\n", data)
            self.assertNotIn(b"\n\t\t" + cli.EID_MARKER.encode()[1:], data)
            text = data[3:].decode("utf-8")
            self.assertIn(cli.EID_MARKER, text)


if __name__ == "__main__":
    unittest.main()
