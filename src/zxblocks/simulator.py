"""Deterministic IR logic reference model; not a Z80 or Spectrum emulator."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable

from .compiler import compile_project
from .keyboard import KEY_MATRIX


class Simulator:
    def __init__(self, project: dict[str, Any]):
        compile_project(project)  # Reuse the compiler's complete validation/limits.
        self.project = deepcopy(project)
        self.names = [variable["name"] for variable in project.get("variables", [])]
        self.variables = {variable["name"].upper(): variable.get("initial", 0)
                          for variable in project.get("variables", [])}
        self.border = 0
        self.frame = 0
        self.started = False
        self.keys: frozenset[str] = frozenset()

    def _sample(self, keys: Iterable[str]) -> None:
        if isinstance(keys, (str, bytes)):
            raise ValueError("keys must be a sequence of physical key names, not a string")
        values = list(keys)
        if any(not isinstance(key, str) for key in values):
            raise ValueError("Physical key names must be strings")
        sampled = frozenset(values)
        unknown = sampled - KEY_MATRIX.keys()
        if unknown:
            raise ValueError(f"Unknown physical keys: {', '.join(sorted(unknown))}")
        self.keys = sampled

    def _value(self, expression: Any) -> int:
        if type(expression) is int:
            return expression
        if "key" in expression:
            return int(expression["key"] in self.keys)
        return self.variables[expression["var"].upper()]

    def _actions(self, actions: list[dict]) -> None:
        for action in actions:
            op = action["op"]
            if op == "set":
                self.variables[action["var"].upper()] = self._value(action["value"])
            elif op == "change":
                name = action["var"].upper()
                self.variables[name] = (self.variables[name] + action["by"]) & 255
            elif op == "call":
                self.border = self._value(action["arg"]) & 7
            elif op == "if":
                left = self.variables[action["condition"]["var"].upper()]
                right = action["condition"]["value"]
                comparisons = {"eq": left == right, "ne": left != right,
                               "lt": left < right, "ge": left >= right}
                branch = "then" if comparisons[action["condition"]["op"]] else "else"
                self._actions(action.get(branch, []))

    def snapshot(self) -> dict:
        return {"frame": self.frame, "border": self.border,
                "variables": {name: self.variables[name.upper()] for name in self.names}}

    def start(self, keys: Iterable[str] = ()) -> dict:
        if self.started:
            raise ValueError("Start event has already run")
        self._sample(keys)
        self._actions(self.project.get("events", {}).get("start", []))
        self.started = True
        return self.snapshot()

    def step(self, keys: Iterable[str] = ()) -> dict:
        if not self.started:
            self.start(keys)
        else:
            self._sample(keys)
        self._actions(self.project.get("events", {}).get("frame", []))
        self.frame += 1
        return self.snapshot()
