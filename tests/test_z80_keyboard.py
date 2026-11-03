"""Execute assembled code against physical keyboard ports, without Spectrum ROM.

Requires sjasmplus and requirements-z80-tests.txt. This checks Z80 code/ports,
not a full 48K machine: IM 1 uses a test-owned IRQ stub and no contention.
"""

import importlib.util
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from zxblocks.compiler import compile_project
from zxblocks.simulator import Simulator as ReferenceSimulator

AVAILABLE = shutil.which("sjasmplus") and importlib.util.find_spec("skoolkit")
ROOT = Path(__file__).resolve().parents[1]

# Independent hardware fixture: physical rows A8..A15, bits D0..D4.
PHYSICAL_ROWS = (
    ("CAPS_SHIFT", "Z", "X", "C", "V"), ("A", "S", "D", "F", "G"),
    ("Q", "W", "E", "R", "T"), ("1", "2", "3", "4", "5"),
    ("0", "9", "8", "7", "6"), ("P", "O", "I", "U", "Y"),
    ("ENTER", "L", "K", "J", "H"), ("SPACE", "SYMBOL_SHIFT", "M", "N", "B"),
)


class Ports:
    def __init__(self):
        self.keys = set()
        self.reads = []
        self.border = 0
        self.release_after_read = False

    def read_port(self, registers, port):
        self.reads.append(port)
        value = 255
        if port & 255 == 254:
            for row, keys in enumerate(PHYSICAL_ROWS):
                if not (port & (1 << (8 + row))):
                    for bit, key in enumerate(keys):
                        if key in self.keys:
                            value &= ~(1 << bit)
        if self.release_after_read:
            self.keys.clear()
        return value

    def write_port(self, registers, port, value, tstates):
        if port & 255 == 254:
            self.border = value & 7


class Machine:
    def __init__(self, project, directory):
        from skoolkit.simulator import Simulator
        from skoolkit.simutils import PC, IFF, T, SP
        self.PC, self.IFF, self.T, self.SP = PC, IFF, T, SP
        source, binary, symbols = [directory / f"program.{suffix}" for suffix in ("asm", "bin", "sym")]
        source.write_text(compile_project(project), encoding="utf-8")
        result = subprocess.run(["sjasmplus", f"--raw={binary.as_posix()}",
                                 f"--sym={symbols.as_posix()}", source.as_posix()],
                                capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        self.labels = {name: int(value, 16) for name, value in
                       re.findall(r"^(\w+): EQU 0x([0-9A-Fa-f]+)", symbols.read_text(), re.M)}
        self.memory = [0] * 65536
        code = binary.read_bytes()
        self.memory[32768:32768 + len(code)] = code
        # Test-owned IRQ handler: let the IRQ pulse expire, then EI / RETI.
        self.memory[56:75] = [0] * 16 + [0xFB, 0xED, 0x4D]
        self.cpu = Simulator(self.memory, {"PC": 32768, "SP": 0x7FFC})
        self.ports = Ports()
        self.cpu.set_tracer(self.ports)
        self.project = project

    def run_until(self, address, interrupts=False):
        for _ in range(50000):
            previous_pc = self.cpu.registers[self.PC]
            self.cpu.run()
            registers = self.cpu.registers
            if interrupts and registers[self.IFF] and registers[self.T] % 69888 < 32:
                self.cpu.accept_interrupt(registers, self.memory, previous_pc)
            if registers[self.PC] == address:
                return
        raise AssertionError("Generated Z80 did not reach the frame boundary")

    def start(self, keys=()):
        self.ports.keys = set(keys)
        self.run_until(self.labels["ZXB_MAIN_LOOP"])

    def step(self, keys=()):
        self.ports.keys = set(keys)
        self.ports.reads.clear()
        self.run_until(self.labels["ZXB_ON_FRAME"], interrupts=True)
        self.run_until(self.labels["ZXB_MAIN_LOOP"])
        if self.cpu.registers[self.SP] != 0x7FFC:
            raise AssertionError("Generated code did not balance the stack")
        return {variable["name"]: self.memory[self.labels[f"ZXB_VAR_{variable['name'].upper()}"]]
                for variable in self.project.get("variables", [])}


@unittest.skipUnless(AVAILABLE, "Requires sjasmplus and pip install -r requirements-z80-tests.txt")
class AssembledKeyboardTests(unittest.TestCase):
    def test_poll_base_cost_against_zilog_instruction_timings(self):
        for keys in (["SPACE"], [row[0] for row in PHYSICAL_ROWS]):
            project = {"format": "zxblocks/v2", "variables": [{"name": "pressed"}],
                       "events": {"frame": [{"op": "set", "var": "pressed", "value": {"key": key}}
                                            for key in keys]}}
            with tempfile.TemporaryDirectory() as directory:
                machine = Machine(project, Path(directory))
                # IM 1 (2 bytes), EI (1 byte), then the startup CALL KEY_POLL.
                call = machine.labels["ZXB_START"] + 3
                machine.cpu.registers[machine.PC] = call
                before = machine.cpu.registers[machine.T]
                machine.run_until(call + 3)
                self.assertEqual(machine.cpu.registers[machine.T] - before, 27 + 35 * len(keys))

    def test_all_40_physical_keys_against_independent_ports_and_ir_model(self):
        keys = [key for row in PHYSICAL_ROWS for key in row]
        actions = [{"op": "set", "var": f"k{i}", "value": {"key": key}} for i, key in enumerate(keys)]
        project = {"format": "zxblocks/v2", "variables": [{"name": f"k{i}"} for i in range(40)],
                   "events": {"start": actions, "frame": actions}}
        with tempfile.TemporaryDirectory() as directory:
            machine = Machine(project, Path(directory))
            reference = ReferenceSimulator(project)
            machine.start(["Q", "SPACE"])
            initial = reference.start(["Q", "SPACE"])["variables"]
            for name, value in initial.items():
                self.assertEqual(machine.memory[machine.labels[f"ZXB_VAR_{name.upper()}"]], value)
            for pressed in [[], *[[key] for key in keys], keys, []]:
                with self.subTest(pressed=pressed):
                    self.assertEqual(machine.step(pressed), reference.step(pressed)["variables"])
                    self.assertEqual(len(machine.ports.reads), 8)
                    self.assertEqual(len(set(machine.ports.reads)), 8)

    def test_example_press_hold_release_matches_reference_border(self):
        project = json.loads((ROOT / "examples/keyboard_border/project.json").read_text(encoding="utf-8"))
        inputs = json.loads((ROOT / "examples/keyboard_border/inputs.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            machine = Machine(project, Path(directory))
            reference = ReferenceSimulator(project)
            machine.start()
            reference.start()
            for keys in inputs:
                expected = reference.step(keys)
                self.assertEqual(machine.step(keys), expected["variables"])
                self.assertEqual(machine.ports.border, expected["border"])
                self.assertEqual(machine.ports.reads, [0x7FFE])

    def test_changes_between_expressions_do_not_resample_the_row(self):
        project = {"format": "zxblocks/v2", "variables": [{"name": "a"}, {"name": "b"}],
                   "events": {"frame": [{"op": "set", "var": name, "value": {"key": "SPACE"}}
                                        for name in ("a", "b")]}}
        with tempfile.TemporaryDirectory() as directory:
            machine = Machine(project, Path(directory))
            machine.start()
            machine.ports.release_after_read = True
            self.assertEqual(machine.step(["SPACE"]), {"a": 1, "b": 1})
            self.assertEqual(machine.ports.reads, [0x7FFE])
