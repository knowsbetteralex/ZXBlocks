# ZXBlocks architecture

## Concept

A Scratch-like editor on PC targeting classic ZX Spectrum 48K. The host is unconstrained; the 48K machine receives only native Z80 code. The M1 Blockly editor and hand-authored JSON use exactly the same IR and Python compiler.

~~~text
Blockly workspace (M1)
         |
         v
zxblocks/v1, v2 or v3 JSON project
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

`POST /api/build` and `/api/run` take the same current project IR. A shared
stdlib runner validates and compiles it, generates a fixed-name snapshot
wrapper, assembles BIN/SNA/SLD with sjasmplus and packages CODE TAP. Run then
starts the locally configured `emuz` executable with the native snapshot path.
`zxblocks run <project.json>` exposes the same runner without the browser.
No IR version, runtime instruction or ABI change is involved in packaging.

The editor now manages named projects with stable IDs in `projects/<id>/`.
It infers capabilities from connected blocks: keyboard expressions promote
authored exports to v2, arithmetic/new comparisons to v3 automatically. Raw IR import and compiler validation
remain strict about the declared version; IR schemas and the runtime ABI do
not change. Removing unused keyboard blocks removes their runtime routines.
Its `zxblocks/editor/v2` container separates Blockly drafts/viewport from an
optional valid compiler IR. Old `zxblocks/editor/v1` files remain importable;
the old browser autosave is migrated explicitly without changing compiler IR.
Revision-checked atomic document saves prevent one tab overwriting another.

Project-scoped build/run requests write immutable numbered jobs under
`build/projects/<id>/`, classified as source, artifacts and debug data. Persistent
manifests support history and verified reuse after a server restart. Only six
known artifacts and logs are exposed, never client-supplied paths or commands.
No shell is used; wrapper directives/filenames remain constants. Failed current
programs never launch stale output. Raw-IR endpoints remain compatible.
See [projects, document migration and build storage](PROJECTS.md) for the schema,
UI workflow, cache inputs, concurrency limits and directory layout.

## Arithmetic foundation before scheduling

v3 adds nested u8 add/sub and unsigned comparisons of two expressions, while
preserving legacy v1/v2 assembly. Expressions compile inline with balanced
stack saves of left operands; no interpreter, helper RAM or new runtime routine
is introduced. The [v3 specification](BLOCK_IR_V3.md) documents the grammar,
expression limits, register/stack contract and migration. The editor, CLI,
reference model and assembled execution use the same documented semantics.

Remaining arithmetic, bitwise and logical operations precede timers/waits and
procedures; see [the arithmetic plan](ARITHMETIC_PLAN.md). Existing runtime
builtin contracts and old-format grammars remain unchanged.

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

Multiplication/division/remainder, bitwise/logical expressions, animation tool, object system,
timer/procedure IR, BASIC loader, T-state profiler, 128K/Next, AY, AI optimizer
and a complete emulator.
