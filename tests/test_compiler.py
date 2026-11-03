"""Tests intentionally need only Python's standard library."""

import copy
import json
import struct
import unittest
from pathlib import Path

from zxblocks.compiler import CompileError, compile_project
from zxblocks.tap import make_code_tap


EXAMPLE = Path(__file__).resolve().parents[1] / "examples/border_cycle/project.json"


class CompilerTests(unittest.TestCase):
    def setUp(self):
        self.project = json.loads(EXAMPLE.read_text(encoding="utf-8"))

    def test_example_generates_entry_events_and_runtime(self):
        asm = compile_project(self.project)
        for fragment in (
            "ORG 32768", "ZXB_START:", "HALT", "ZXB_ON_FRAME:",
            "INC A", "CP 8", "JP C,ZXB_ELSE_", "OUT (254),A",
            "ZXB_VAR_COUNTER:", "DB 0",
        ):
            self.assertIn(fragment, asm)
        self.assertEqual(asm, compile_project(self.project))

    def test_unknown_variable_rejected(self):
        self.project["events"]["frame"][0]["var"] = "missing"
        with self.assertRaises(CompileError):
            compile_project(self.project)

    def test_byte_range_rejected(self):
        self.project["variables"][0]["initial"] = 256
        with self.assertRaises(CompileError):
            compile_project(self.project)

    def test_nested_if_with_else(self):
        self.project["events"]["frame"] = [
            {"op": "if", "condition": {"var": "counter", "op": "eq", "value": 1},
             "then": [{"op": "set", "var": "counter", "value": 2}],
             "else": [{"op": "set", "var": "counter", "value": 3}]}
        ]
        asm = compile_project(self.project)
        self.assertIn("JP NZ,ZXB_ELSE_", asm)
        self.assertIn("ZXB_ENDIF_", asm)

    def test_invalid_assembly_identifier_rejected(self):
        self.project["variables"][0]["name"] = "X: JP 0"
        with self.assertRaises(CompileError):
            compile_project(self.project)

    def test_no_unused_border_runtime(self):
        self.project["events"]["frame"] = []
        self.assertNotIn("ZXB_RT_SET_BORDER:", compile_project(self.project))

    def test_tap_blocks_and_checksums(self):
        image = make_code_tap(bytes([0x00, 0xC9]), "DEMO")
        self.assertEqual(struct.unpack_from("<H", image, 0)[0], 19)
        header = image[2:21]
        self.assertEqual(header[1], 3)
        self.assertEqual(header[2:12], b"DEMO      ")
        self.assertEqual(header[12:14], b"\x02\x00")
        self.assertEqual(header[14:16], b"\x00\x80")
        self.assertEqual(self._xor(header), 0)
        data_size = struct.unpack_from("<H", image, 21)[0]
        data = image[23:23 + data_size]
        self.assertEqual(data, bytes([255, 0, 0xC9, 0x36]))
        self.assertEqual(self._xor(data), 0)

    @staticmethod
    def _xor(data):
        check = 0
        for byte in data:
            check ^= byte
        return check


if __name__ == "__main__":
    unittest.main()
