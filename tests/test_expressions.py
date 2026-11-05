"""v3 expression semantics, compatibility, migration and assembled execution."""

import contextlib
import copy
import hashlib
import io
import json
import random
import tempfile
import unittest
from pathlib import Path

from zxblocks.cli import main
from zxblocks.compiler import CompileError, compile_project
from zxblocks.migrate import upgrade_project, upgrade_to_v2
from zxblocks.simulator import Simulator
from test_z80_keyboard import AVAILABLE, Machine

ROOT = Path(__file__).resolve().parents[1]


def binary(op, left, right):
    return {"op": op, "left": left, "right": right}


def project_for(value):
    return {"format": "zxblocks/v3", "variables": [{"name": "x"}],
            "events": {"frame": [{"op": "set", "var": "x", "value": value}]}}


class ExpressionTests(unittest.TestCase):
    def test_existing_v1_v2_assembly_stays_byte_identical(self):
        fingerprints = {"border_cycle": "9c632a5d89e848e61a4debcf2e2c0f48532e2376a80172099d1441c80c4c9bf3",
                        "keyboard_border": "3fcf62c2433f3669c5cf5ce168dca41fee0e6ae09eaae17951707f1344248d88"}
        for name, expected in fingerprints.items():
            project = json.loads((ROOT / f"examples/{name}/project.json").read_text(encoding="utf-8"))
            self.assertEqual(hashlib.sha256(compile_project(project).encode()).hexdigest(), expected)

    def test_wraps_at_each_node_and_preserves_subtraction_order(self):
        for expression, expected in [
            (binary("add", 255, 1), 0), (binary("sub", 0, 1), 255),
            (binary("sub", binary("add", 255, 2), binary("sub", 0, 1)), 2),
            (binary("sub", 20, binary("sub", 10, 3)), 13),
            (binary("sub", binary("sub", 20, 10), 3), 7),
        ]:
            with self.subTest(expression=expression):
                project = project_for(expression)
                self.assertEqual(Simulator(project).step()["variables"]["x"], expected)
                self.assertEqual(compile_project(project), compile_project(project))

    def test_older_formats_reject_new_nodes_and_new_comparisons(self):
        for version in ("zxblocks/v1", "zxblocks/v2"):
            project = project_for(binary("add", 1, 2)); project["format"] = version
            with self.assertRaisesRegex(CompileError, "v3"):
                compile_project(project)
            project["events"]["frame"] = [{"op": "if", "condition": {"left": 1, "op": "eq", "right": 1}}]
            with self.assertRaisesRegex(CompileError, "v3"):
                compile_project(project)

    def test_invalid_operators_operands_and_extra_fields_are_rejected(self):
        invalid = [binary("mul", 1, 2), binary([], 1, 2), binary('add\n INCLUDE "evil"', 1, 2),
                   {"op": "add", "left": 1}, {**binary("add", 1, 2), "extra": 0},
                   binary("add", True, 2), binary("sub", 1, -1), binary("add", 256, 0),
                   binary("add", {"var": "missing"}, 0), binary("sub", None, 0)]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(CompileError):
                compile_project(project_for(value))
        for condition in ({"left": 0, "op": "gt"}, {"left": 0, "op": {}, "right": 1},
                          {"left": 0, "op": "eq", "right": 1, "var": "x"},
                          {"var": "x", "op": "le", "value": 1}):
            project = project_for(0)
            project["events"]["frame"] = [{"op": "if", "condition": condition}]
            with self.subTest(condition=condition), self.assertRaises(CompileError):
                compile_project(project)

    def test_exact_nested_diagnostic_and_depth_boundary(self):
        project = project_for(binary("add", 1, binary("sub", {"var": "bad"}, 0)))
        with self.assertRaises(CompileError) as caught:
            compile_project(project)
        self.assertEqual(caught.exception.path, "events.frame[0].value.right.left")
        expression = 1
        for _ in range(16):
            expression = binary("add", 0, expression)
        self.assertEqual(Simulator(project_for(expression)).step()["variables"]["x"], 1)
        with self.assertRaisesRegex(CompileError, "expression depth"):
            compile_project(project_for(binary("sub", expression, 0)))

    def test_expression_node_budget_is_shared_by_comparison_operands_and_events(self):
        project = project_for(0)
        condition = {"left": 0, "op": "eq", "right": 0}
        project["events"] = {"start": [{"op": "set", "var": "x", "value": 0}],
                             "frame": [{"op": "if", "condition": condition} for _ in range(2048)]}
        with self.assertRaisesRegex(CompileError, "expression nodes"):
            compile_project(project)

    def test_migration_is_explicit_non_mutating_idempotent_and_never_downgrades(self):
        for name in ("border_cycle", "keyboard_border"):
            original = json.loads((ROOT / f"examples/{name}/project.json").read_text(encoding="utf-8"))
            before = copy.deepcopy(original)
            upgraded = upgrade_project(original, "zxblocks/v3")
            self.assertEqual(original, before)
            self.assertEqual(upgraded["format"], "zxblocks/v3")
            self.assertEqual(compile_project(original), compile_project(upgraded))
            self.assertEqual(upgrade_project(upgraded, "zxblocks/v3"), upgraded)
            with self.assertRaisesRegex(ValueError, "Downgrading"):
                upgrade_to_v2(upgraded)

    def test_cli_upgrade_v3_and_simulation(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "upgraded.json"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["upgrade", str(ROOT / "examples/border_cycle/project.json"),
                                       "--to", "zxblocks/v3", "-o", str(output)]), 0)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["format"], "zxblocks/v3")
            output.write_text(json.dumps(project_for(binary("sub", 0, 1))), encoding="utf-8")
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                self.assertEqual(main(["simulate", str(output), "--frames", "1"]), 0)
            self.assertEqual(json.loads(stream.getvalue())[0]["variables"]["x"], 255)


@unittest.skipUnless(AVAILABLE, "Requires sjasmplus and optional SkoolKit")
class AssembledExpressionTests(unittest.TestCase):
    def test_add_sub_and_all_unsigned_comparisons_against_independent_values(self):
        operators = ("eq", "ne", "lt", "le", "gt", "ge")
        a, b = {"var": "a"}, {"var": "b"}
        actions = [{"op": "set", "var": "sum", "value": binary("add", a, b)},
                   {"op": "set", "var": "difference", "value": binary("sub", a, b)},
                   {"op": "set", "var": "nested", "value": binary("sub", a, binary("sub", b, 7))}]
        for operator in operators:
            actions.append({"op": "if", "condition": {"left": binary("add", a, 1), "op": operator,
                                                        "right": binary("sub", b, 1)},
                            "then": [{"op": "set", "var": operator, "value": 1}],
                            "else": [{"op": "set", "var": operator, "value": 0}]})
        names = ["a", "b", "sum", "difference", "nested", *operators]
        project = {"format": "zxblocks/v3", "variables": [{"name": name} for name in names], "events": {"frame": actions}}
        rng = random.Random(9481)
        boundaries = [0, 1, 2, 7, 127, 128, 254, 255]
        pairs = [(a, b) for a in boundaries for b in boundaries] + [(rng.randrange(256), rng.randrange(256)) for _ in range(512)]
        with tempfile.TemporaryDirectory() as directory:
            machine = Machine(project, Path(directory)); machine.start()
            for a, b in pairs:
                machine.memory[machine.labels["ZXB_VAR_A"]] = a
                machine.memory[machine.labels["ZXB_VAR_B"]] = b
                # Invoke the compiled event directly with an owned return sentinel.
                machine.memory[0x7FFA:0x7FFC] = [0, 1]
                machine.cpu.registers[machine.SP] = 0x7FFA
                machine.cpu.registers[machine.PC] = machine.labels["ZXB_ON_FRAME"]
                machine.run_until(0x100)
                self.assertEqual(machine.cpu.registers[machine.SP], 0x7FFC)
                actual = {name: machine.memory[machine.labels[f"ZXB_VAR_{name.upper()}"]] for name in names}
                left, right = (a + 1) & 255, (b - 1) & 255
                expected = {"a": a, "b": b, "sum": (a + b) % 256, "difference": (a - b) % 256,
                            "nested": (a - ((b - 7) % 256)) % 256,
                            "eq": int(left == right), "ne": int(left != right), "lt": int(left < right),
                            "le": int(left <= right), "gt": int(left > right), "ge": int(left >= right)}
                self.assertEqual(actual, expected, (a, b))

    def test_example_with_keyboard_and_interrupts_matches_reference(self):
        project = json.loads((ROOT / "examples/arithmetic_border/project.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            machine = Machine(project, Path(directory)); machine.start()
            reference = Simulator(project); reference.start()
            for keys in ([[]] * 20 + [["SPACE"]] * 20 + [[]] * 20):
                state = reference.step(keys)
                self.assertEqual(machine.step(keys), state["variables"])
                self.assertEqual(machine.ports.border, state["border"])

    def test_maximum_depth_comparison_is_stack_balanced_and_within_contract(self):
        expression = {"var": "x"}
        for _ in range(16):
            expression = binary("sub", 1, expression)
        project = project_for(3)
        project["events"]["frame"] = [{"op": "if", "condition": {"left": 3, "op": "eq", "right": expression},
                                         "then": [{"op": "set", "var": "x", "value": 7}]}]
        with tempfile.TemporaryDirectory() as directory:
            machine = Machine(project, Path(directory)); machine.start()
            machine.memory[machine.labels["ZXB_VAR_X"]] = 3
            machine.memory[0x7FFA:0x7FFC] = [0, 1]
            machine.cpu.registers[machine.SP] = 0x7FFA
            machine.cpu.registers[machine.PC] = machine.labels["ZXB_ON_FRAME"]
            lowest = 0x7FFA
            for _ in range(2000):
                machine.cpu.run(); lowest = min(lowest, machine.cpu.registers[machine.SP])
                if machine.cpu.registers[machine.PC] == 0x100:
                    break
            else:
                self.fail("Expression event did not return")
            self.assertEqual(machine.cpu.registers[machine.SP], 0x7FFC)
            self.assertEqual(lowest, 0x7FFA - 34)
            self.assertEqual(machine.memory[machine.labels["ZXB_VAR_X"]], 7)
