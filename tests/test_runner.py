"""Generic snapshot builds and launching current projects without fixed examples."""

import contextlib
import io
import json
import shutil
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from zxblocks.cli import main
from zxblocks.compiler import CompileError, compile_project
from zxblocks.runner import BuildError, BuildResult, SNAPSHOT_SOURCE, build_project, launch_emulator

ROOT = Path(__file__).resolve().parents[1]
PROJECT = json.loads((ROOT / "examples/keyboard_border/project.json").read_text(encoding="utf-8"))


class BuildFailureTests(unittest.TestCase):
    def test_invalid_ir_never_creates_output_or_runs_tools(self):
        with tempfile.TemporaryDirectory() as directory, patch("zxblocks.runner.subprocess.run") as run:
            output = Path(directory) / "output"
            with self.assertRaises(CompileError):
                build_project({"format": "unknown"}, output)
            self.assertFalse(output.exists())
            run.assert_not_called()

    def test_missing_assembler_is_actionable(self):
        with tempfile.TemporaryDirectory() as directory, patch("zxblocks.runner.shutil.which", return_value=None):
            with self.assertRaisesRegex(BuildError, "PATH"):
                build_project(PROJECT, Path(directory) / "output")

    def test_failed_assembly_cannot_reuse_an_old_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "project.sna").write_bytes(b"stale snapshot")
            with patch("zxblocks.runner.require_tool", return_value="sjasmplus"), \
                 patch("zxblocks.runner.subprocess.run", return_value=Mock(returncode=1, stderr="assembly failed", stdout="")):
                with self.assertRaisesRegex(BuildError, "assembly failed"):
                    build_project(PROJECT, output)
            self.assertFalse((output / "project.sna").exists())

    def test_timeout_is_bounded_and_reported(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch("zxblocks.runner.require_tool", return_value="sjasmplus"), \
             patch("zxblocks.runner.subprocess.run", side_effect=subprocess.TimeoutExpired("sjasmplus", 30)):
            with self.assertRaisesRegex(BuildError, "30 seconds"):
                build_project(PROJECT, Path(directory))

    def test_missing_outputs_fail_even_when_assembler_returns_success(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch("zxblocks.runner.require_tool", return_value="sjasmplus"), \
             patch("zxblocks.runner.subprocess.run", return_value=Mock(returncode=0, stdout="", stderr="")):
            with self.assertRaisesRegex(BuildError, "BIN/SNA/SLD"):
                build_project(PROJECT, Path(directory))

    def test_emulator_receives_native_snapshot_path_without_a_shell(self):
        with tempfile.TemporaryDirectory() as directory:
            result = BuildResult(Path(directory), 72)
            result.snapshot.write_bytes(b"test fixture")
            with patch("zxblocks.runner.require_tool", return_value="emuz.exe"), \
                 patch("zxblocks.runner.subprocess.Popen") as popen:
                launch_emulator(result)
                argv = popen.call_args.args[0]
                self.assertEqual(argv, ["emuz.exe", str(result.snapshot.resolve())])
                self.assertNotIn("shell", popen.call_args.kwargs)

    def test_run_cli_builds_the_selected_project_not_a_fixed_example(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "custom.json"
            project = {"format": "zxblocks/v1", "name": "My own project"}
            source.write_text(json.dumps(project), encoding="utf-8")
            with patch("zxblocks.runner.require_tool"), \
                 patch("zxblocks.runner.build_project", return_value=BuildResult(Path(directory), 25)) as build, \
                 patch("zxblocks.runner.launch_emulator", return_value=Mock(pid=1234)) as launch, \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["run", str(source)]), 0)
            self.assertEqual(build.call_args.args[0], project)
            self.assertEqual(build.call_args.args[1], Path("build/cli") / source.parent.name)
            launch.assert_called_once()
            self.assertEqual(json.loads(source.read_text(encoding="utf-8")), project)

    def test_build_default_classifies_cli_outputs_by_source_directory(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.chdir(directory):
            source = Path("my_game/project.json")
            source.parent.mkdir()
            source.write_text(json.dumps(PROJECT), encoding="utf-8")
            def assemble(argv, **kwargs):
                Path(argv[1].removeprefix("--raw=")).write_bytes(b"\x00")
            with patch("zxblocks.cli.subprocess.run", side_effect=assemble), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["build", str(source)]), 0)
            output = Path("build/cli/my_game")
            self.assertTrue((output / "my_game.asm").is_file())
            self.assertTrue((output / "my_game.tap").is_file())
            self.assertFalse(Path("build/my_game.asm").exists())


@unittest.skipUnless(shutil.which("sjasmplus"), "Requires sjasmplus for real snapshot build tests")
class NativeBuildTests(unittest.TestCase):
    def test_generic_v1_v2_v3_builds_preserve_code_and_create_valid_snapshots(self):
        for example in ("border_cycle", "keyboard_border", "arithmetic_border"):
            with self.subTest(example=example), tempfile.TemporaryDirectory() as directory:
                project = json.loads((ROOT / f"examples/{example}/project.json").read_text(encoding="utf-8"))
                output = Path(directory) / "output with spaces"
                result = build_project(project, output)
                self.assertTrue(all(file.is_file() for file in result.files))
                self.assertEqual((output / "project.asm").read_text(encoding="utf-8"), compile_project(project))
                control = Path(directory) / "control.bin"
                subprocess.run(["sjasmplus", f"--raw={control.as_posix()}", (output / "project.asm").as_posix()],
                               capture_output=True, check=True)
                binary = (output / "project.bin").read_bytes()
                self.assertEqual(binary, control.read_bytes())
                self.assertEqual(result.code_size, len(binary))
                sna = result.snapshot.read_bytes()
                self.assertEqual(len(sna), 49179)
                sp = struct.unpack_from("<H", sna, 23)[0]
                self.assertEqual(sp + 2, 0x7FFC)
                self.assertEqual(struct.unpack_from("<H", sna, 27 + sp - 16384)[0], 32768)
                self.assertEqual(sna[27 + 16384:27 + 16384 + len(binary)], binary)
                self.assertEqual((output / "project.tap").read_bytes()[24:-1], binary)
                self.assertIn("ZXB_START", (output / "project.sld").read_text(encoding="utf-8"))

    def test_project_title_cannot_become_an_assembler_filename_or_directive(self):
        project = {"format": "zxblocks/v1", "name": '../escape"\nINCLUDE "evil.asm'}
        with tempfile.TemporaryDirectory() as directory:
            result = build_project(project, Path(directory))
            self.assertEqual((result.directory / "_snapshot.asm").read_text(encoding="utf-8"), SNAPSHOT_SOURCE)
            self.assertNotIn("evil.asm", (result.directory / "project.asm").read_text(encoding="utf-8"))
            self.assertEqual(json.loads((result.directory / "project.json").read_text(encoding="utf-8")), project)
