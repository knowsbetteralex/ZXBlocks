# ZXBlocks architecture

## Concept

A Scratch-like editor on PC targeting classic ZX Spectrum 48K. The host is unconstrained; the 48K machine receives only native Z80 code. First milestone takes hand-authored JSON and emits ASM/TAP; future UI will generate exactly the same IR.

~~~text
Blockly workspace (later)
         |
         v
zxblocks/v1 JSON project
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

- Editor: visual blocks, sprites/animations and workspace state; serializes versioned project IR only.
- Compiler: semantic checks, symbol table, types, deterministic Z80, diagnostics, links runtime functions.
- Runtime: standalone Z80 procedures for input, graphics, event scheduling, objects, animation and collisions.
- Packager: currently CODE TAP; later BASIC autostart and other target formats.
- Tests: unit tests for compiler/IR; assembler/emulator integration after bootstrap.

## Execution

Current generated game calls the start event, then repeats HALT -> frame event. It expects a valid BASIC stack and 48K IM1 ROM interrupts.

Future game loop: HALT -> RENDER_FRAME -> KEY_POLL -> UPDATE_GAME. Event blocks update model state, not screen RAM directly. A Scratch-style wait must compile to a non-blocking timer/state machine. Multiple scripts become deterministic cooperative state machines, not OS threads.

## Performance and memory

The bitmap/attributes occupy the conventional 48K display memory. Default program origin is 32768; track RAM for code, state, stack and resource tables. Precompute shifted sprites and masks on PC; include only referenced runtime routines; derive memory and T-state budgets from actual output. Use emulator traces for verified timing rather than claiming guarantees from incomplete static cost estimates.

## Compatibility

IR format is versioned; design a migration strategy before adding breaking changes. Runtime contracts must be hardware-aware. Existing SpaceCan procedures may be selectively adapted only after interface/licensing review. Keep Delta-C-specific assumptions in separate target profiles.

## Not in bootstrap

Visual editor, animation tool, object system, BASIC loader, T-state profiler, 128K/Next, AY, AI optimizer and a complete emulator.
