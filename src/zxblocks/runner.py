"""Build a standalone 48K snapshot and launch a configured local emulator.

All assembler filenames/directives are fixed. Project names and client paths
are never interpolated into assembler text or shell commands.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .compiler import compile_project
from .tap import make_code_tap

ARTIFACT_NAMES = tuple(f"project.{suffix}" for suffix in ("json", "asm", "bin", "tap", "sna", "sld"))
SNAPSHOT_SOURCE = """; Generated snapshot packaging; no additional Z80 instructions.
        DEVICE ZXSPECTRUM48, 32767
        SLDOPT COMMENT WPMEM, LOGPOINT, ASSERTION
        INCLUDE "project.asm"
        SAVESNA "project.sna", ZXB_START
"""


class BuildError(ValueError):
    """A local build or emulator could not be completed."""


@dataclass(frozen=True)
class BuildResult:
    directory: Path
    code_size: int

    @property
    def snapshot(self) -> Path:
        return self.directory / "project.sna"

    @property
    def files(self) -> tuple[Path, ...]:
        return tuple(self.directory / name for name in ARTIFACT_NAMES)


def require_tool(command: str) -> str:
    executable = shutil.which(command)
    if not executable:
        raise BuildError(f"Tool '{command}' was not found. Add it to PATH and restart the editor server.")
    return executable


def build_project(project: Any, directory: Path, assembler: str = "sjasmplus") -> BuildResult:
    """Package current IR as fixed project.* files in an explicitly chosen directory."""
    asm = compile_project(project)  # Validate before creating or overwriting files.
    executable = require_tool(assembler)
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    for suffix in ("bin", "tap", "sna", "sld"):
        (directory / f"project.{suffix}").unlink(missing_ok=True)
    (directory / "project.json").write_text(json.dumps(project, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (directory / "project.asm").write_text(asm, encoding="utf-8")
    (directory / "_snapshot.asm").write_text(SNAPSHOT_SOURCE, encoding="utf-8")
    try:
        result = subprocess.run(
            [executable, "--fullpath=rel", "--raw=project.bin", "--sld=project.sld", "_snapshot.asm"],
            cwd=directory, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
        )
    except subprocess.TimeoutExpired as exc:
        raise BuildError("sjasmplus did not finish within 30 seconds") from exc
    except OSError as exc:
        raise BuildError(f"Could not start sjasmplus: {exc}") from exc
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()[-4000:]
        raise BuildError(f"sjasmplus failed: {detail}")
    required = ("project.bin", "project.sna", "project.sld")
    if any(not (directory / name).is_file() for name in required):
        raise BuildError("sjasmplus did not create the required BIN/SNA/SLD files")
    binary = (directory / "project.bin").read_bytes()
    if not binary or len(binary) > 32768:
        raise BuildError("Program must fit in the 32768 bytes above address 32768")
    if (directory / "project.sna").stat().st_size != 49179:
        raise BuildError("Assembler did not create a standard 48K SNA snapshot")
    (directory / "project.tap").write_bytes(make_code_tap(binary, "ZXBLOCKS"))
    return BuildResult(directory, len(binary))


def launch_emulator(result: BuildResult, emulator: str = "emuz") -> subprocess.Popen:
    executable = require_tool(emulator)
    if not result.snapshot.is_file():
        raise BuildError("Build a snapshot before launching the emulator")
    try:
        # Native Path spelling is intentional: EmuZWin misparses E:/... paths.
        return subprocess.Popen(
            [executable, str(result.snapshot.resolve())], stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        raise BuildError(f"Could not start {emulator}: {exc}") from exc
