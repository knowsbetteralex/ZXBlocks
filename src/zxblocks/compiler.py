"""Deterministic JSON block IR to readable sjasmplus Z80 assembly.

MVP deliberately supports only unsigned 8-bit variables and a small,
well-defined instruction set. No user-controlled text is emitted as ASM.
"""

from __future__ import annotations

import re
from typing import Any

IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
MAX_DEPTH = 16
MAX_ACTIONS = 4096


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
        if project.get("format") != "zxblocks/v1":
            raise CompileError("Expected format: zxblocks/v1")
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
        self.uses_border = False

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

    def load_a(self, expression: Any) -> None:
        if isinstance(expression, dict) and set(expression) == {"var"}:
            self.emit(f"LD A,({self.var_label(expression['var'])})")
        else:
            self.emit(f"LD A,{_byte(expression, 'expression')}")

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
            self.load_a(statement.get("value"))
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
            variable = self.var_label(cond.get("var"))
            number = _byte(cond.get("value"), "if.condition.value")
            inverse = {"eq": "NZ", "ne": "Z", "lt": "NC", "ge": "C"}
            cmp_op = cond.get("op")
            if not isinstance(cmp_op, str) or cmp_op not in inverse:
                raise CompileError("Comparison must be eq, ne, lt or ge")
            then = statement.get("then", [])
            otherwise = statement.get("else", [])
            if not isinstance(then, list) or not isinstance(otherwise, list):
                raise CompileError("if.then and if.else must be arrays")
            skip = self.fresh_label("ELSE")
            self.emit(f"LD A,({variable})")
            self.emit(f"CP {number}")
            self.emit(f"JP {inverse[cmp_op]},{skip}")
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
            self.load_a(statement.get("arg"))
            self.emit("CALL ZXB_RT_SET_BORDER")
        else:
            raise CompileError(f"Unsupported action: {op!r}")

    def compile(self) -> str:
        self.lines.extend([
            "; Generated by ZXBlocks. Edit project JSON, not this file.",
            "; Entry: CLEAR 32767; LOAD \"\" CODE",
            "        ORG 32768",
        ])
        self.label("ZXB_START")
        self.emit("IM 1")
        self.emit("EI")
        self.emit("CALL ZXB_ON_START")
        self.label("ZXB_MAIN_LOOP")
        self.emit("HALT")
        self.emit("CALL ZXB_ON_FRAME")
        self.emit("JP ZXB_MAIN_LOOP")
        for name in ("start", "frame"):
            self.lines.append("")
            self.label(f"ZXB_ON_{name.upper()}")
            self.actions(self.events[name], path=f"events.{name}")
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
        self.lines.append("")
        self.label("ZXB_END")
        return "\n".join(self.lines) + "\n"


def compile_project(project: Any) -> str:
    """Compile a parsed zxblocks/v1 project to Z80 assembly."""
    return _Compiler(project).compile()
