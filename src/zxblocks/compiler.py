"""Deterministic JSON block IR to readable sjasmplus Z80 assembly.

MVP deliberately supports only unsigned 8-bit variables and a small,
well-defined instruction set. No user-controlled text is emitted as ASM.
"""

from __future__ import annotations

import re
from typing import Any

from .keyboard import KEY_MATRIX, KEY_ROWS
from .formats import KEYBOARD_FORMATS, SUPPORTED_FORMATS

IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
MAX_DEPTH = 16
MAX_ACTIONS = 4096
MAX_EXPRESSION_DEPTH = 16
MAX_EXPRESSION_NODES = 4096


class CompileError(ValueError):
    """Invalid project/block IR."""

    def __init__(self, message: str, path: str | None = None):
        super().__init__(message)
        self.path = path


def _byte(value: Any, context: str) -> int:
    if type(value) is not int or not 0 <= value <= 255:
        raise CompileError(f"{context}: expected integer from 0 to 255")
    return value


class _Compiler:
    def __init__(self, project: Any):
        if not isinstance(project, dict):
            raise CompileError("Project must be a JSON object")
        self.format = project.get("format")
        if self.format not in SUPPORTED_FORMATS:
            raise CompileError("Expected format: " + ", ".join(SUPPORTED_FORMATS))
        variables = project.get("variables", [])
        if not isinstance(variables, list):
            raise CompileError("variables must be an array")
        self.variables: dict[str, int] = {}
        for index, variable in enumerate(variables):
            if not isinstance(variable, dict):
                raise CompileError(f"variables[{index}] must be an object")
            name = variable.get("name")
            if not isinstance(name, str) or not IDENTIFIER.fullmatch(name):
                raise CompileError(f"variables[{index}].name: invalid identifier")
            normalized = name.upper()
            if normalized in self.variables:
                raise CompileError(f"Duplicate variable: {name}")
            self.variables[normalized] = _byte(
                variable.get("initial", 0), f"variables[{index}].initial"
            )
        events = project.get("events", {})
        if not isinstance(events, dict):
            raise CompileError("events must be an object")
        extra = set(events) - {"start", "frame"}
        if extra:
            raise CompileError(f"Unsupported events: {', '.join(sorted(extra))}")
        self.events = {}
        for name in ("start", "frame"):
            statements = events.get(name, [])
            if not isinstance(statements, list):
                raise CompileError(f"events.{name} must be an array")
            self.events[name] = statements
        self.lines: list[str] = []
        self.label_index = 0
        self.action_count = 0
        self.expression_count = 0
        self.uses_border = False
        self.key_rows: set[int] = set()

    def emit(self, instruction: str) -> None:
        self.lines.append(f"        {instruction}")

    def label(self, name: str) -> None:
        self.lines.append(f"{name}:")

    def fresh_label(self, prefix: str) -> str:
        self.label_index += 1
        return f"ZXB_{prefix}_{self.label_index}"

    def var_label(self, name: Any) -> str:
        if not isinstance(name, str) or name.upper() not in self.variables:
            raise CompileError(f"Unknown variable: {name!r}")
        return f"ZXB_VAR_{name.upper()}"

    def load_a(self, expression: Any, path: str | None = None, depth: int = 0) -> None:
        self.expression_count += 1
        if depth > MAX_EXPRESSION_DEPTH:
            raise CompileError("Maximum expression depth is 16", path)
        if self.expression_count > MAX_EXPRESSION_NODES:
            raise CompileError("Too many expression nodes (maximum 4096)", path)
        try:
            self._expression(expression, path, depth)
        except CompileError as exc:
            if exc.path is None:
                exc.path = path
            raise

    def _expression(self, expression: Any, path: str | None, depth: int) -> None:
        if isinstance(expression, dict) and set(expression) == {"var"}:
            self.emit(f"LD A,({self.var_label(expression['var'])})")
        elif isinstance(expression, dict) and set(expression) == {"key"}:
            if self.format not in KEYBOARD_FORMATS:
                raise CompileError("Key expressions require zxblocks/v2 or v3; upgrade explicitly")
            key = expression["key"]
            if not isinstance(key, str) or key not in KEY_MATRIX:
                raise CompileError(f"Unknown physical key: {key!r}")
            row, bit = KEY_MATRIX[key]
            self.key_rows.add(row)
            self.emit(f"LD A,(ZXB_KEY_ROW_{row:02X})")
            self.emit("CPL")
            self.emit(f"AND {1 << bit}")
            for _ in range(bit):
                self.emit("RRCA")
        elif isinstance(expression, dict) and "op" in expression:
            if self.format != "zxblocks/v3":
                raise CompileError("Arithmetic expressions require zxblocks/v3; upgrade explicitly")
            if set(expression) != {"op", "left", "right"}:
                raise CompileError("Arithmetic expression must contain only op, left and right")
            operator = expression["op"]
            if not isinstance(operator, str) or operator not in ("add", "sub"):
                raise CompileError("Arithmetic operator must be add or sub")
            self.load_a(expression["left"], f"{path}.left", depth + 1)
            self.emit("PUSH AF")
            self.load_a(expression["right"], f"{path}.right", depth + 1)
            self.emit("LD C,A")
            self.emit("POP AF")
            self.emit("ADD A,C" if operator == "add" else "SUB C")
        else:
            self.emit(f"LD A,{_byte(expression, 'expression')}")

    def compare_condition(self, condition: dict, path: str, skip: str) -> None:
        if "left" not in condition and "right" not in condition:
            # Preserve the original legacy instructions and four-operator ABI.
            if self.format == "zxblocks/v3" and set(condition) != {"var", "op", "value"}:
                raise CompileError("Legacy condition must contain only var, op and value", path)
            variable = self.var_label(condition.get("var"))
            number = _byte(condition.get("value"), "if.condition.value")
            inverse = {"eq": "NZ", "ne": "Z", "lt": "NC", "ge": "C"}
            operator = condition.get("op")
            if not isinstance(operator, str) or operator not in inverse:
                raise CompileError("Comparison must be eq, ne, lt or ge")
            self.emit(f"LD A,({variable})")
            self.emit(f"CP {number}")
            self.emit(f"JP {inverse[operator]},{skip}")
            return
        if self.format != "zxblocks/v3":
            raise CompileError("Expression comparisons require zxblocks/v3; upgrade explicitly", path)
        if set(condition) != {"left", "op", "right"}:
            raise CompileError("Expression condition must contain only left, op and right", path)
        operator = condition["op"]
        if not isinstance(operator, str) or operator not in ("eq", "ne", "lt", "le", "gt", "ge"):
            raise CompileError("Comparison must be eq, ne, lt, le, gt or ge", path + ".op")
        self.load_a(condition["left"], path + ".left")
        self.emit("PUSH AF")
        self.load_a(condition["right"], path + ".right")
        self.emit("LD C,A")
        self.emit("POP AF")
        self.emit("CP C")
        if operator == "gt":
            self.emit(f"JP C,{skip}")
            self.emit(f"JP Z,{skip}")
        elif operator == "le":
            passed = self.fresh_label("CMP_TRUE")
            self.emit(f"JP C,{passed}")
            self.emit(f"JP NZ,{skip}")
            self.label(passed)
        else:
            inverse = {"eq": "NZ", "ne": "Z", "lt": "NC", "ge": "C"}
            self.emit(f"JP {inverse[operator]},{skip}")

    def actions(self, statements: list[Any], depth: int = 0, path: str = "") -> None:
        """Attach the innermost IR action path to diagnostics for editors."""
        if depth > MAX_DEPTH:
            raise CompileError("Maximum nesting depth exceeded", path)
        for index, statement in enumerate(statements):
            action_path = f"{path}[{index}]"
            try:
                self._action(statement, depth, action_path)
            except CompileError as exc:
                if exc.path is None:
                    exc.path = action_path
                raise

    def _action(self, statement: Any, depth: int, path: str) -> None:
        self.action_count += 1
        if self.action_count > MAX_ACTIONS:
            raise CompileError("Too many actions")
        if not isinstance(statement, dict):
            raise CompileError("Action must be an object")
        op = statement.get("op")
        if op == "set":
            variable = self.var_label(statement.get("var"))
            self.load_a(statement.get("value"), path + ".value" if self.format == "zxblocks/v3" else None)
            self.emit(f"LD ({variable}),A")
        elif op == "change":
            variable = self.var_label(statement.get("var"))
            delta = statement.get("by")
            if type(delta) is not int or not -255 <= delta <= 255:
                raise CompileError("change.by must be an integer -255..255")
            if delta:
                self.emit(f"LD A,({variable})")
                if delta == 1:
                    self.emit("INC A")
                elif delta == -1:
                    self.emit("DEC A")
                else:
                    self.emit(f"ADD A,{delta & 255}")
                self.emit(f"LD ({variable}),A")
        elif op == "if":
            cond = statement.get("condition")
            if not isinstance(cond, dict):
                raise CompileError("if.condition must be an object")
            then = statement.get("then", [])
            otherwise = statement.get("else", [])
            if not isinstance(then, list) or not isinstance(otherwise, list):
                raise CompileError("if.then and if.else must be arrays")
            skip = self.fresh_label("ELSE")
            self.compare_condition(cond, path + ".condition", skip)
            self.actions(then, depth + 1, f"{path}.then")
            if otherwise:
                end = self.fresh_label("ENDIF")
                self.emit(f"JP {end}")
                self.label(skip)
                self.actions(otherwise, depth + 1, f"{path}.else")
                self.label(end)
            else:
                self.label(skip)
        elif op == "call":
            if statement.get("name") != "set_border":
                raise CompileError(f"Unknown procedure: {statement.get('name')!r}")
            self.uses_border = True
            self.load_a(statement.get("arg"), path + ".arg" if self.format == "zxblocks/v3" else None)
            self.emit("CALL ZXB_RT_SET_BORDER")
        else:
            raise CompileError(f"Unsupported action: {op!r}")

    def compile(self) -> str:
        # Compile event bodies first to discover required keyboard rows. Their
        # final position/label order stays identical for existing v1 projects.
        for name in ("start", "frame"):
            self.lines.append("")
            self.label(f"ZXB_ON_{name.upper()}")
            self.actions(self.events[name], path=f"events.{name}")
            self.emit("RET")
        event_lines = self.lines
        self.lines = []
        self.lines.extend([
            "; Generated by ZXBlocks. Edit project JSON, not this file.",
            "; Entry: CLEAR 32767; LOAD \"\" CODE",
            "        ORG 32768",
        ])
        self.label("ZXB_START")
        self.emit("IM 1")
        self.emit("EI")
        if self.key_rows:
            self.emit("CALL ZXB_RT_KEY_POLL")
        self.emit("CALL ZXB_ON_START")
        self.label("ZXB_MAIN_LOOP")
        self.emit("HALT")
        if self.key_rows:
            self.emit("CALL ZXB_RT_KEY_POLL")
        self.emit("CALL ZXB_ON_FRAME")
        self.emit("JP ZXB_MAIN_LOOP")
        self.lines.extend(event_lines)
        if self.key_rows:
            self.lines.extend([
                "", "; Keyboard snapshot: inputs none; outputs active-low row bytes.",
                "; Clobbers A, BC, flags; stack 2 bytes for CALL; classic 48K ULA.",
                "; Base cost incl. CALL: 27 + 35*rows T-states; contention unmeasured.",
            ])
            self.label("ZXB_RT_KEY_POLL")
            for row, _ in KEY_ROWS:
                if row in self.key_rows:
                    self.emit(f"LD BC,${row:02X}FE")
                    self.emit("IN A,(C)")
                    self.emit(f"LD (ZXB_KEY_ROW_{row:02X}),A")
            self.emit("RET")
        if self.uses_border:
            self.lines.append("")
            self.label("ZXB_RT_SET_BORDER")
            self.emit("AND 7")
            self.emit("OUT (254),A")
            self.emit("RET")
        if self.variables:
            self.lines.append("")
            self.lines.append("; Unsigned 8-bit variables")
            for name, value in self.variables.items():
                self.label(f"ZXB_VAR_{name}")
                self.emit(f"DB {value}")
        if self.key_rows:
            self.lines.extend(["", "; Keyboard rows owned by ZXB_RT_KEY_POLL"])
            for row, _ in KEY_ROWS:
                if row in self.key_rows:
                    self.label(f"ZXB_KEY_ROW_{row:02X}")
                    self.emit("DB 255")
        self.lines.append("")
        self.label("ZXB_END")
        return "\n".join(self.lines) + "\n"


def compile_project(project: Any) -> str:
    """Compile a parsed supported versioned project to Z80 assembly."""
    return _Compiler(project).compile()
