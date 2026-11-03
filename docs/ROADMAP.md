# Roadmap

The checkboxes separate completed work from plans.

## M0 — bootstrap

- [x] Repo layout, architecture decisions, AGENTS.md and PR workflow.
- [x] JSON to readable Z80 ASM with strict u8 checks.
- [x] Start/frame, set/change/if and border runtime.
- [x] CODE-only TAP writer and Python unit tests/CI definition.
- [x] Verify actual sjasmplus assembly and 48K emulator behavior.
- [x] Review and merge initial PR (#1, bootstrap commit `71737c6`).
- [x] VS Code build tasks, DeZog 48K snapshot/source debugging and EmuZWin launch.

Acceptance: tests pass, deterministic ASM; after manually loading CODE, border cycles on a real/emulated 48K.

Verified on 2026-11-04: Python 3.13.5, all 7 bootstrap unit tests passed;
sjasmplus 1.21.0 assembled the example (52-byte BIN, 77-byte TAP). Repeated
builds matched byte for byte. The user confirmed the program runs in an
emulator; DeZog's ZX48K simulator was also checked for border changes,
instruction stepping and a breakpoint in `ZXB_ON_FRAME`. SNA entry/stack and
SLD source mappings were verified. No timing or contention measurements yet.

## M1 — visual editor

- [ ] Pin a version of Blockly and document third-party licenses.
- [ ] Toolbox/workspace for supported nodes, import/export zxblocks/v1.
- [ ] Preserve editor layout separately from semantic IR.
- [ ] Show compiler errors tied to blocks.
- [ ] Convert the border example in both directions.

Acceptance: Blockly-authored border example matches hand-written IR behavior.

## M2 — timing and events

- [ ] Key input expressions, non-blocking timers, cooperative scheduling.
- [ ] Named procedures and object state.
- [ ] Python reference simulation to test logic independently from video.

Acceptance: deterministic input-driven movement can be unit-tested.

## M3 — graphics/animations

- [ ] Z80 sprite rendering and background restoration with dirty flags.
- [ ] Sprite/animation timeline editor with masks and compile-time shifts.
- [ ] Frame loop HALT -> RENDER_FRAME -> KEY_POLL -> UPDATE_GAME.
- [ ] Ship moves with animated sprite in 48K emulator.

## M4 — object game

- [ ] Bullet pool, enemy objects, collisions before drawing.
- [ ] Separate dynamic background and object layers.
- [ ] Resource budgets (RAM/T-states) and emulator measurement.
- [ ] Review reusable SpaceCan routines before integrating.

## M5 — polish

- [ ] BASIC autostart loader and distribution.
- [ ] Example gallery, source maps, per-block profiling.
- [ ] Windows packaging and reproducible release builds.

## Suggested first Codex tasks

1. Bootstrap verified; repeat the assembler/emulator smoke test when Z80 behavior changes.
2. Create Blockly MVP with exact zxblocks/v1 import/export and tests.
3. Add keyboard and frame timer support with IR specification and tests first.
4. Implement runtime ABI documentation and initial sprite vertical slice.

One small PR per task. Do not jump to M4 without working M1/M2 tests.
