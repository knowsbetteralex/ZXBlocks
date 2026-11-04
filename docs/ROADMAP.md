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

- [x] Pin Blockly 13.4.0 and document third-party licenses.
- [x] Toolbox/workspace for supported nodes, import/export zxblocks/v1.
- [x] Preserve editor layout separately from semantic IR.
- [x] Show compiler action errors tied to blocks; project errors remain global.
- [x] Convert the border example in both directions, including identical Python-generated ASM.
- [x] Local stdlib Python editor host, pinned frontend build and CI checks.
- [x] Build/run the current editor project directly; generic CLI run and TAP/SNA downloads.
- [x] Project list, clear Open/Save/Run toolbar, grouped menu and safe project switching.
- [x] Filesystem draft saving, separate recovery per project and explicit editor-container migration.
- [x] Per-project numbered/classified builds, persistent history and verified build reuse.
- [x] Infer capabilities from connected blocks, automatically select required IR version and remove the manual selector.
- [x] Keep the page footer after the editor in responsive document flow.
- [ ] Browser acceptance of project switching, draft restore, menu, downloads and run.
- [ ] Interactive browser smoke test: import/edit/export, workspace restore, compile and error navigation.

Acceptance: Blockly-authored border example matches hand-written IR behavior.

Implementation: `feat/blockly-editor`. All 13 Blockly tests and 15 Python tests
passed on 2026-11-04. Automated checks cover real headless
Blockly workspaces, variable renaming, nested actions, independent layout,
invalid input preservation, diagnostic mapping and the Python HTTP API.
The example exported from an actual Blockly workspace was built with the CLI
and sjasmplus: ASM, BIN and TAP matched the verified M0 artifacts byte for byte.
Build/run workflow verified on 2026-11-04: 50 Python tests and 16 Blockly tests
passed locally, including generic v1/v2 snapshot assembly and HTTP build/run
contracts. A custom project was submitted to `/api/run`: its 73-byte BIN,
48K SNA entry/stack and six artifact downloads were checked; EmuZWin launched
the snapshot in Spectrum 48K mode and reported responsive. Source JSON and
workspace hashes stayed unchanged. This confirms the backend/process route,
not a browser-button or visual emulator test. Computer Use's native pipe and
browser host were unavailable for that UI verification.
Interactive browser acceptance is still pending: on 2026-11-04 Computer Use
stopped because it could not reliably determine Chrome's current URL. See
`editor/README.md` for startup, verification and known limitations. Complete
that smoke test before marking M1 accepted. CLI/compiler M2 work can be tested
independently while browser automation is unavailable; it does not close M1.

Project-workspace iteration: menu/toolbar, multiple saved projects, editor/v2
draft migration, revision conflicts and numbered classified builds are implemented
in `feat/project-workspace`; see `docs/PROJECTS.md`. Existing build outputs were
preserved in a legacy archive; example tasks/debug presets now use
`build/examples/`. Interactive review of this iteration remains unchecked:
Computer Use reported an unavailable native pipe and browser access host.
Verification on 2026-11-04: 61 Python and 21 real-Blockly/persistence tests passed;
the frontend bundle built. Both relocated example/DeZog snapshots assembled
without errors or warnings. An isolated project-store HTTP smoke test imported
a real Blockly document for the user's program, downloaded all six artifacts,
checked its 73-byte BIN and 48K SNA entry/stack, reused its build for EmuZWin
launch and again after restarting the API host. EmuZWin reported responsive in
Spectrum 48K mode; input source files were unchanged. This is backend/process
evidence, not a visual or browser-click acceptance test.

Follow-up in `fix/editor-features-footer`: connected keyboard blocks now
automatically promote editor exports/saves to v2; raw IR import and the Python
compiler still validate declared versions strictly. The manual format selector
was removed. 61 Python tests and 24 Blockly/persistence tests passed. An isolated
Chrome headless check exercised three window sizes with 20 added variables and
40 build-history rows: the history scrolls inside its panel, the footer follows
the editor and remains reachable at the page bottom, without horizontal page
overflow or JavaScript errors. A full interactive menu/import/run acceptance
test remains open; Computer Use's native/browser hosts were unavailable.

## M2 — expressions, input and scheduling

Priority agreed on 2026-11-04: complete arithmetic and expression operations
before timers/delays. The detailed sequence, open semantic decisions and
acceptance checks are in [the arithmetic plan](ARITHMETIC_PLAN.md).

### M2.1 — arithmetic and expressions (next)

- [ ] Specify/version the expression IR extension and migrations, preserving v1/v2.
- [ ] Nested addition/subtraction and comparisons between expressions (=, !=, <, <=, >, >=).
- [ ] Multiplication, unsigned integer division and remainder, with specified zero-divisor behavior.
- [ ] Bitwise AND/OR/XOR/NOT, logical shifts and documented shift-count rules.
- [ ] Logical condition composition, distinct from bitwise byte operations.
- [ ] Blockly blocks, automatic capability selection, IR round trips and incomplete-expression draft restore.
- [ ] Reference-model, compatibility and assembled-code tests; runnable arithmetic example.

Acceptance: the operations work from blocks through compiled execution, with
matching u8 semantics and documented error/boundary behavior. Complete this
stage before starting timers or waits; implement one complete slice at a time.

### M2.2 — keyboard and reference simulation

- [x] Versioned key input expressions, per-frame row samples and explicit v1→v2 migration.
- [x] Keyboard-border example, Blockly round trips and assembled Z80 port tests.
- [x] Python reference simulation for v1/v2 actions and keyboard input, independent of video.
- [ ] Interactive 48K emulator keyboard test and browser keyboard-block smoke test.

### M2.3 — timers, delays and procedures (after arithmetic)

- [ ] Periodic events such as "every N frames" without blocking keyboard/frame updates.
- [ ] Non-blocking waits and cooperative scheduling.
- [ ] Named procedures and object state.

M2 acceptance: deterministic expression/input/timer behavior can be tested
against compiled execution; waiting scripts do not stop the other updates.

Keyboard slice implemented in `feat/keyboard-v2`; see `docs/BLOCK_IR_V2.md`
and `docs/KEYBOARD_RUNTIME.md`. General arithmetic and bitwise nodes,
timers/procedures/object semantics are not yet implemented. Interactive Chrome
automation was blocked again on 2026-11-04
because Computer Use could not reliably determine its current URL. No new
browser or full 48K keyboard-emulator run is claimed; the assembled-code
tests use an owned IRQ stub and port fixture, not the Spectrum ROM or ULA.

Verification on 2026-11-04: 35 Python tests (including 4 assembled-code tests
with sjasmplus 1.21.0 / SkoolKit 10.1) and 16 real-Blockly tests passed; no
local test skips. Both examples assembled with no errors or warnings. The
keyboard BIN is 72 bytes; SNA entry/stack/code and SLD symbols were checked.
The existing v1 ASM/BIN/TAP still match the verified M0 artifacts byte for byte.
The dedicated assembled-keyboard CI job is added; a remote CI run is not claimed.
Also fixed Windows HTTP port sharing: a second editor cannot bind the same
active port and accidentally serve an older compiler; covered by a regression test.

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

## Next implementation tasks

1. Implement nested `+`/`-` and comparisons of expressions as a complete versioned IR/compiler/simulator/editor slice.
2. Complete multiplication, division/remainder, bitwise operations and logical conditions, including their boundary rules and arithmetic examples.
3. Add periodic events, then non-blocking waits and user procedures after the arithmetic acceptance checks pass.
4. Implement runtime ABI documentation and the first moving sprite.

Keep the pending editor/keyboard interactive acceptance checks visible and
repeat assembler/emulator checks when generated Z80 behavior changes.

One small PR per task. Do not jump to M4 without working M1/M2 tests.
