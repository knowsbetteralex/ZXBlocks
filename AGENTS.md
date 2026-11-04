# AGENTS.md — Codex instructions

Project: ZXBlocks, a visual programming compiler for classic ZX Spectrum 48K.
Before any architectural change read README.md, docs/ARCHITECTURE.md, docs/BLOCK_IR.md, docs/ROADMAP.md.

## Collaboration

- Use short-lived feature branches and focused PRs to main; never force-push main.
- For each PR describe purpose, changes, tests actually performed and known limitations.
- Keep a working end-to-end example at every commit and update docs alongside code.
- Do not silently change the agreed IR or runtime ABI. Version changes and migrations explicitly.
- Prioritize readability, clear names, small units and correctness before T-state optimization.
- Do not claim assembler or emulator tests ran without evidence.

## Layers

1. editor/ — Blockly GUI; it emits versioned JSON IR, never assembly directly.
2. src/zxblocks/ — validation, code generation, packaging and CLI.
3. runtime/ — eventual Z80 library, linked only when needed.
4. examples/ and tests/ — executable test cases.

The IR is the boundary between editor and compiler. Do not commit generated ASM/BIN/TAP artifacts unless explicitly approved as test fixtures.

## Compiler invariants

- Supported input formats are zxblocks/v1 and the documented zxblocks/v2
  keyboard extension (docs/BLOCK_IR_V2.md). Preserve v1 behavior and reject
  unsupported nodes. The editor automatically promotes authored programs to
  v2 when connected blocks require it; raw v1 JSON still rejects v2-only nodes.
- Never eval input or interpolate arbitrary user text into ASM.
- Deterministic output, stable labels, human-readable assembly and strict identifier checks.
- MVP only supports unsigned bytes; change arithmetic wraps modulo 256.
- Guard recursive depth and number of actions.
- Isolate future manual Z80 ASM extensions behind an explicitly advanced feature.
- Keep Python CLI independently usable and minimize third-party dependencies.

## Spectrum runtime constraints

- Baseline classic 48K, IM 1 interrupts, code at 32768 and HALT-driven frame loop.
- The Spectrum runs native code, not a block interpreter.
- MVP has no renderer. When implementing it prefer:
  HALT -> RENDER_FRAME -> KEY_POLL -> UPDATE_GAME.
- Planned game runtime: background/object layers, no visual overlap between objects,
  collisions resolved before drawing, independent per-object dirty flags.
- Each ASM routine needs a contract: input/output, clobbered registers/flags, stack,
  RAM ownership, hardware requirements and measured/estimated T-states.
- No ZX Next or 128K-only instructions in the default target.
- Delta-C-specific timing belongs in a target profile, not shared Z80 semantics.
- Do not guess cycle counts or memory contention.

## Quality gates

Run:
1. python -m pip install -e .
2. python -m unittest discover -s tests -v
3. python -m zxblocks compile examples/border_cycle/project.json -o build/border_cycle.asm

When changing Z80 behavior, assemble with sjasmplus and test in a 48K emulator if available; otherwise clearly declare that test unperformed. No secrets, Spectrum ROM files or local machine paths.

## Work order

1. Verify bootstrap assembly and emulator behavior.
2. Add Blockly MVP with IR export/import tests.
3. Complete versioned u8 arithmetic, expression comparisons, bitwise operations
   and logical conditions before timers/waits (docs/ARITHMETIC_PLAN.md).
4. Extend scheduling with non-blocking timers/waits and user procedures,
   preserving keyboard/frame updates.
5. Design a documented Z80 runtime ABI and integrate a moving sprite.
6. Measure RAM and worst-case T-states with emulator instrumentation.

Prefer one complete vertical slice over a broad unfinished framework.
