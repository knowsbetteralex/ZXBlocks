"""Version compatibility, keyboard semantics and independent logic traces."""

import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

from zxblocks.cli import main
from zxblocks.compiler import CompileError, compile_project
from zxblocks.keyboard import KEY_MATRIX
from zxblocks.migrate import upgrade_to_v2
from zxblocks.simulator import Simulator

ROOT = Path(__file__).resolve().parents[1]


def project_for(key="SPACE", format="zxblocks/v2"):
    return {"format": format, "variables": [{"name": "pressed", "initial": 0}],
            "events": {"frame": [{"op": "set", "var": "pressed", "value": {"key": key}}]}}


class KeyboardCompilerTests(unittest.TestCase):
    def test_physical_matrix_has_40_unique_keys(self):
        self.assertEqual(len(KEY_MATRIX), 40)
        self.assertEqual(KEY_MATRIX["SPACE"], (0x7F, 0))
        self.assertEqual(KEY_MATRIX["Q"], (0xFB, 0))
        self.assertEqual(KEY_MATRIX["P"], (0xDF, 0))
        self.assertEqual(KEY_MATRIX["B"], (0x7F, 4))

    def test_v1_requires_explicit_upgrade_for_keys(self):
        with self.assertRaisesRegex(CompileError, "upgrade explicitly"):
            compile_project(project_for(format="zxblocks/v1"))

    def test_migration_is_non_mutating_and_preserves_existing_asm(self):
        original = json.loads((ROOT / "examples/border_cycle/project.json").read_text(encoding="utf-8"))
        before = copy.deepcopy(original)
        upgraded = upgrade_to_v2(original)
        self.assertEqual(original, before)
        self.assertEqual(upgraded["format"], "zxblocks/v2")
        self.assertEqual(compile_project(original), compile_project(upgraded))
        self.assertEqual(upgrade_to_v2(upgraded), upgraded)

    def test_unsupported_formats_and_invalid_key_shapes_are_rejected(self):
        for key in ("space", "BREAK", "SPACE: JP 0", [], {}, None, 1):
            with self.subTest(key=key), self.assertRaises(CompileError):
                compile_project(project_for(key))
        for version in ("zxblocks/v0", "zxblocks/v99"):
            with self.assertRaises(CompileError):
                compile_project(project_for(format=version))
        project = project_for()
        project["events"]["frame"][0]["value"]["var"] = "pressed"
        with self.assertRaises(CompileError):
            compile_project(project)

    def test_rows_sampled_once_per_frame_and_before_start(self):
        project = project_for("SPACE")
        project["events"]["start"] = [{"op": "set", "var": "pressed", "value": {"key": "B"}}]
        asm = compile_project(project)
        self.assertEqual(asm.count("IN A,(C)"), 1)
        self.assertEqual(asm.count("CALL ZXB_RT_KEY_POLL"), 2)
        self.assertIn("HALT\n        CALL ZXB_RT_KEY_POLL\n        CALL ZXB_ON_FRAME", asm)
        self.assertIn("LD BC,$7FFE", asm)
        self.assertIn("CPL\n        AND 16\n        RRCA\n        RRCA\n        RRCA\n        RRCA", asm)

    def test_unreferenced_rows_and_runtime_are_not_linked(self):
        asm = compile_project({"format": "zxblocks/v2"})
        self.assertNotIn("ZXB_KEY_ROW", asm)
        self.assertNotIn("ZXB_RT_KEY_POLL", asm)
        self.assertNotIn("ZXB_KEY_ROW_FE", compile_project(project_for()))


class SimulatorTests(unittest.TestCase):
    def test_press_hold_release_trace(self):
        project = json.loads((ROOT / "examples/keyboard_border/project.json").read_text(encoding="utf-8"))
        simulator = Simulator(project)
        trace = [simulator.step(keys) for keys in ([], ["SPACE"], ["SPACE"], [], ["Q"], ["Q", "SPACE"])]
        self.assertEqual([state["border"] for state in trace], [1, 6, 6, 1, 1, 6])
        self.assertEqual([state["variables"]["space_pressed"] for state in trace], [0, 1, 1, 0, 0, 1])

    def test_all_keys_independent_and_simultaneous(self):
        for key in KEY_MATRIX:
            with self.subTest(key=key):
                simulator = Simulator(project_for(key))
                self.assertEqual(simulator.step([])["variables"]["pressed"], 0)
                self.assertEqual(simulator.step([key])["variables"]["pressed"], 1)
                self.assertEqual(simulator.step(KEY_MATRIX)["variables"]["pressed"], 1)
                self.assertEqual(simulator.step([])["variables"]["pressed"], 0)

    def test_start_event_runs_once_with_initial_input_snapshot(self):
        project = project_for()
        project["events"]["start"] = [{"op": "set", "var": "pressed", "value": {"key": "SPACE"}}]
        project["events"]["frame"] = [{"op": "change", "var": "pressed", "by": 1}]
        simulator = Simulator(project)
        self.assertEqual(simulator.step(["SPACE"])["variables"]["pressed"], 2)
        self.assertEqual(simulator.step([])["variables"]["pressed"], 3)
        with self.assertRaises(ValueError):
            simulator.start()

    def test_v1_logic_wraps_and_unsigned_comparisons(self):
        simulator = Simulator({"format": "zxblocks/v1", "variables": [{"name": "x", "initial": 255}],
                               "events": {"frame": [{"op": "change", "var": "X", "by": 1},
                                 {"op": "if", "condition": {"var": "x", "op": "lt", "value": 1},
                                  "then": [{"op": "call", "name": "set_border", "arg": 255}]}]}})
        self.assertEqual(simulator.step()["variables"]["x"], 0)
        self.assertEqual(simulator.border, 7)

    def test_unknown_and_malformed_key_inputs_fail(self):
        for keys in ("SPACE", ["space"], [1], ["BREAK"]):
            with self.subTest(keys=keys), self.assertRaises(ValueError):
                Simulator(project_for()).step(keys)

    def test_snapshot_and_project_do_not_alias_internal_state(self):
        project = project_for()
        simulator = Simulator(project)
        project["events"]["frame"].clear()
        state = simulator.step(["SPACE"])
        state["variables"]["pressed"] = 200
        self.assertEqual(simulator.snapshot()["variables"]["pressed"], 1)


class KeyboardCliTests(unittest.TestCase):
    def test_simulation_cli_uses_per_frame_inputs(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = main(["simulate", str(ROOT / "examples/keyboard_border/project.json"),
                           "--inputs", str(ROOT / "examples/keyboard_border/inputs.json")])
        self.assertEqual(result, 0)
        self.assertEqual([state["border"] for state in json.loads(output.getvalue())], [1, 6, 6, 1, 1, 6])

    def test_upgrade_cli_writes_separate_versioned_project(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "upgraded.json"
            with contextlib.redirect_stdout(io.StringIO()):
                result = main(["upgrade", str(ROOT / "examples/border_cycle/project.json"), "-o", str(output)])
            self.assertEqual(result, 0)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["format"], "zxblocks/v2")
