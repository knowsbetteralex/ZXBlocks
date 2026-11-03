"""ZXBlocks command-line entry point."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from .compiler import CompileError, compile_project
from .tap import make_code_tap


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="zxblocks")
    commands = parser.add_subparsers(dest="command", required=True)
    compile_cmd = commands.add_parser("compile", help="Generate readable Z80 ASM")
    compile_cmd.add_argument("project", type=Path)
    compile_cmd.add_argument("-o", "--output", type=Path, required=True)
    build_cmd = commands.add_parser("build", help="Build ASM, binary and CODE TAP")
    build_cmd.add_argument("project", type=Path)
    build_cmd.add_argument("-o", "--output-dir", type=Path, default=Path("build"))
    build_cmd.add_argument("--assembler", default="sjasmplus")
    editor_cmd = commands.add_parser("editor", help="Serve the local Blockly editor")
    editor_cmd.add_argument("--port", type=int, default=8765)
    editor_cmd.add_argument("--open", action="store_true", help="Open the editor in a browser")
    args = parser.parse_args(argv)

    try:
        if args.command == "editor":
            from .editor import serve_editor
            serve_editor(args.port, args.open)
            return 0
        with args.project.open("r", encoding="utf-8") as source:
            project = json.load(source)
        asm = compile_project(project)
        if args.command == "compile":
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(asm, encoding="utf-8")
            print(f"Generated: {args.output}")
        else:
            args.output_dir.mkdir(parents=True, exist_ok=True)
            stem = args.project.parent.name or "game"
            asm_path = args.output_dir / f"{stem}.asm"
            bin_path = args.output_dir / f"{stem}.bin"
            tap_path = args.output_dir / f"{stem}.tap"
            asm_path.write_text(asm, encoding="utf-8")
            subprocess.run(
                [args.assembler, f"--raw={bin_path.resolve().as_posix()}", asm_path.as_posix()],
                check=True,
            )
            tap_path.write_bytes(make_code_tap(bin_path.read_bytes(), stem.upper()))
            print(f"Generated: {asm_path}, {bin_path}, {tap_path}")
    except (OSError, json.JSONDecodeError, CompileError, ValueError,
            subprocess.CalledProcessError) as exc:
        print(f"ZXBlocks error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
