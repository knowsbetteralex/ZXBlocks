# ZXBlocks architecture

## Concept

A Scratch-like editor on PC targeting classic ZX Spectrum 48K. The host is unconstrained; the 48K machine receives only native Z80 code. The M1 Blockly editor and hand-authored JSON use exactly the same IR and Python compiler.

~~~text
Blockly workspace (M1)
         |
         v
zxblocks/v1 or v2 JSON project
         |
         v
validate -> typed IR -> Z80 code generator
                            |
                            +--> required runtime routines (later)
                            |
                            v
                   readable .asm
                            |
                        sjasmplus
                            |
                        .bin / .tap
                            |
                         ZX 48K
~~~

## Components

- Editor: current IR blocks, variable editing and independent workspace state; serializes versioned project IR only. Sprites/animations are planned.
- Compiler: semantic checks, symbol table, types, deterministic Z80, diagnostics, links runtime functions.
- Runtime: standalone Z80 procedures for input, graphics, event scheduling, objects, animation and collisions.
- Packager: currently CODE TAP; later BASIC autostart and other target formats.
- Tests: Python compiler/HTTP tests, headless Blockly round trips and cross-language ASM equality; assembler and 48K emulator smoke tests.

## Local editor host

`python -m zxblocks editor` serves the bundled editor on loopback only, using
Python's standard library. `POST /api/compile` accepts the normal project IR
and returns ASM or a diagnostic with an action path such as
`events.frame[1].then[0]`. The browser maps those paths to Blockly block IDs;
IDs and positions are never inserted into semantic IR. Build the frontend
with the pinned npm dependencies; no Node service or external CDN is needed
while editing. The Python compiler remains independently usable.

Workspace files use a separate `zxblocks/editor/v1` envelope with `project`,
Blockly `workspace` state and initial values keyed by editor variable IDs.
Workspace restore validates the semantic snapshot before replacing the open
project. Normal JSON exports contain only `zxblocks/v1` project data.

## Execution

Current generated game calls the start event, then repeats HALT -> frame event. It expects a valid BASIC stack and 48K IM1 ROM interrupts.

The v2 keyboard slice polls referenced hardware rows before start and between
HALT and the frame event. Expressions read those cached bytes; v1 output stays
unchanged. An independent Python logic simulator accepts per-frame key sets;
it is not a Spectrum emulator. See `BLOCK_IR_V2.md` and `KEYBOARD_RUNTIME.md`.

Future game loop: HALT -> RENDER_FRAME -> KEY_POLL -> UPDATE_GAME. Event blocks update model state, not screen RAM directly. A Scratch-style wait must compile to a non-blocking timer/state machine. Multiple scripts become deterministic cooperative state machines, not OS threads.

## Performance and memory

The bitmap/attributes occupy the conventional 48K display memory. Default program origin is 32768; track RAM for code, state, stack and resource tables. Precompute shifted sprites and masks on PC; include only referenced runtime routines; derive memory and T-state budgets from actual output. Use emulator traces for verified timing rather than claiming guarantees from incomplete static cost estimates.

## Compatibility

IR format is versioned; design a migration strategy before adding breaking changes. Runtime contracts must be hardware-aware. Existing SpaceCan procedures may be selectively adapted only after interface/licensing review. Keep Delta-C-specific assumptions in separate target profiles.

## Still planned

Animation tool, object system, timer/procedure IR, BASIC loader, T-state profiler, 128K/Next, AY, AI optimizer and a complete emulator.
