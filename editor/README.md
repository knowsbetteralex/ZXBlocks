# Blockly editor — M1

The editor supports the existing `zxblocks/v1` semantics. It generates JSON,
never assembly; the local Python compiler generates ASM. No IR version or
runtime ABI change is required.

## Run from a repository checkout

Python 3.11+, the installed ZXBlocks package, and Node.js 22+ are required.
In `editor/`, run `npm ci`, `npm test`, and `npm run build`. From the repository
root, run `python -m zxblocks editor --open` (activate `.venv` first, or use its
Python executable). The server binds only to `127.0.0.1:8765`; `--port` changes
the port. Ctrl+C stops it. VS Code also provides the `ZXBlocks: editor` task.
The compiler API and static assets share one local origin; no remote service
or CDN is required. sjasmplus is needed for CLI BIN/TAP builds, not for editing.

## Working with projects

- The border-cycle example opens initially and can be restored with the example button.
- Import/export uses the normal project JSON, preserving action and declaration order.
- Supported blocks: start/frame, set/change, if/else with eq/ne/lt/ge, set_border,
  byte literals and variable references. All variables are unsigned bytes.
- Add variables and edit their initial values in the project panel. Renaming
  updates references. Remove a variable after removing/replacing its uses.
- The compiler button returns Python-generated ASM. Action diagnostics resolve
  to a block via an editor-only source map; the error button selects that block.
- Save/open a workspace file to preserve positions, IDs, collapsed state and
  the project. The envelope format `zxblocks/editor/v1` is separate from the IR.
  The browser also autosaves the last **valid, connected** workspace.

Invalid imports are checked before replacing the open project. Unknown fields,
nodes, events and versions are rejected rather than silently dropped. Export
normalizes omitted optional arrays/defaults and reference spelling to the
declared variable name; it preserves program semantics, not arbitrary JSON
formatting or unsupported extension fields. Disabled/detached blocks are
reported rather than silently omitted.

## Files and boundaries

- `src/blocks.js`: block definitions and toolbox.
- `src/ir.js`: import validation and existing IR limits.
- `src/workspace.js`: Blockly ↔ IR and independent editor-state serialization.
- `src/app.js`, `index.html`, `src/styles.css`: browser UI; no Z80 generator.
- `src/zxblocks/editor.py` in the repository: stdlib HTTP host, `/api/compile`.
- `tests/`: real headless Blockly round trips, layout persistence, diagnostics,
  variable changes and a cross-language comparison of generated ASM.
- `scripts/build.mjs`: esbuild bundle, local media, license notices and example.

Blockly 13.4.0 and esbuild 0.28.2 are pinned with a lockfile. See
[third-party notices](THIRD_PARTY_NOTICES.md) for licenses. `dist/` and
`node_modules/` are generated and ignored by Git.

## Current limits and verification

There is no in-browser Spectrum emulator, TAP builder, sprite editor, keyboard
IR or timer support. Download JSON and use the existing CLI/DeZog/EmuZWin tasks
for a Spectrum run. The server serves a built repository checkout; standalone
Python wheels do not include editor assets. Changes to frontend sources require
`npm run build` and a page reload.

An incomplete/detached workspace cannot be exported or saved as a valid project;
browser autosave retains the previous valid state. Save a valid workspace file
before clearing browser data. Diagnostics for project/variable declarations
appear globally; diagnostics for actions identify their blocks.

On 2026-11-04 automated Python HTTP/diagnostic tests and real Blockly headless
tests passed, including ASM equality with the hand-written border example.
The browser bundle was built. **Interactive browser/visual QA remains pending:**
Computer Use stopped because it could not establish the current Chrome URL.
No interactive browser test is claimed.
