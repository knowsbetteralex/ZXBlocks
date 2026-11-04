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
    run_cmd = commands.add_parser("run", help="Build any project as a 48K snapshot and open EmuZWin")
    run_cmd.add_argument("project", type=Path)
    run_cmd.add_argument("-o", "--output-dir", type=Path, default=Path("build/run"))
    run_cmd.add_argument("--assembler", default="sjasmplus")
    run_cmd.add_argument("--emulator", default="emuz")
    editor_cmd = commands.add_parser("editor", help="Serve the local Blockly editor")
    editor_cmd.add_argument("--port", type=int, default=8765)
    editor_cmd.add_argument("--open", action="store_true", help="Open the editor in a browser")
    upgrade_cmd = commands.add_parser("upgrade", help="Explicitly upgrade project IR to zxblocks/v2")
    upgrade_cmd.add_argument("project", type=Path)
    upgrade_cmd.add_argument("-o", "--output", type=Path, required=True)
    simulate_cmd = commands.add_parser("simulate", help="Run deterministic IR logic (not a Spectrum emulator)")
    simulate_cmd.add_argument("project", type=Path)
    simulation = simulate_cmd.add_mutually_exclusive_group()
    simulation.add_argument("--frames", type=int, default=60)
    simulation.add_argument("--inputs", type=Path, help="JSON array of pressed key-name arrays, one per frame")
    args = parser.parse_args(argv)

    try:
        if args.command == "editor":
            from .editor import serve_editor
            serve_editor(args.port, args.open)
            return 0
        with args.project.open("r", encoding="utf-8") as source:
            project = json.load(source)
        if args.command == "run":
            from .runner import build_project, launch_emulator, require_tool
            require_tool(args.emulator)
            result = build_project(project, args.output_dir, args.assembler)
            process = launch_emulator(result, args.emulator)
            print(f"Built {result.code_size} code bytes in {result.directory}")
            print(f"Launched {args.emulator}: {result.snapshot} (PID {process.pid})")
            return 0
        if args.command == "upgrade":
            from .migrate import upgrade_to_v2
            upgraded = upgrade_to_v2(project)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(upgraded, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"Upgraded to zxblocks/v2: {args.output}")
            return 0
        if args.command == "simulate":
            from .simulator import Simulator
            if args.inputs:
                inputs = json.loads(args.inputs.read_text(encoding="utf-8"))
                if not isinstance(inputs, list) or len(inputs) > 10000 or any(not isinstance(keys, list) for keys in inputs):
                    raise ValueError("Simulation inputs must be an array of up to 10000 key-name arrays")
            else:
                if not 0 <= args.frames <= 10000:
                    raise ValueError("Simulation frames must be 0..10000")
                inputs = [[] for _ in range(args.frames)]
            simulator = Simulator(project)
            print(json.dumps([simulator.step(keys) for keys in inputs], ensure_ascii=False, indent=2))
            return 0
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
