# Blockly editor — M1

The editor supports `zxblocks/v1` and the explicit `zxblocks/v2` keyboard
extension. It generates JSON, never assembly; the local Python compiler
generates ASM. Existing v1 runtime output is unchanged.

## Run from a repository checkout

Python 3.11+, the installed ZXBlocks package, and Node.js 22+ are required.
In `editor/`, run `npm ci`, `npm test`, and `npm run build`. From the repository
root, run `python -m zxblocks editor --open` (activate `.venv` first, or use its
Python executable). The server binds only to `127.0.0.1:8765`; `--port` changes
the port. Ctrl+C stops it. VS Code also provides the `ZXBlocks: editor` task.
The compiler API and static assets share one local origin; no remote service
or CDN is required. sjasmplus is needed for CLI BIN/TAP builds, not for editing.

## Working with projects

- The last active project reopens; a first launch creates a copy of the border example.
- **Открыть** lists saved projects and imports files; clicking the current project
  name opens the same list. **Сохранить** / Ctrl+S writes the complete editor
  document to `projects/<id>/`. Autosaving also retains incomplete drafts and
  waits before switching projects. A separate browser recovery belongs to each ID.
- **Меню** groups new/duplicate, examples, complete-project/IR export, build,
  ASM inspection and fit-to-view. Examples always create a new editable project.
- Import/export uses the normal project JSON, preserving action and declaration order.
- Supported blocks: start/frame, set/change, if/else with eq/ne/lt/ge, set_border,
  byte literals and variable references. All variables are unsigned bytes.
- In v2, the key-pressed block is a byte expression (1/0). Use the project format
  selector to explicitly choose v2, or open the keyboard-border example.
  v1 rejects key blocks without silently upgrading. The 40 physical key names
  match the Python target; they are not composed BASIC symbols.
- Add variables and edit their initial values in the project panel. Renaming
  updates references. Remove a variable after removing/replacing its uses.
- **Запустить** builds the current in-memory IR and opens its SNA in EmuZWin.
  No JSON download/copy, hard-coded example path or manual ASM wrapper is needed.
  `sjasmplus` and `emuz` must be on the editor server's PATH.
- **Меню → Собрать TAP / SNA** builds without launching. The **Сборки** tab
  shows only the active project's numbered history, downloads and logs, and can
  explicitly launch an earlier snapshot. Source, artifacts and debug data live
  separately under `build/projects/<id>/<number>/`. History survives a server
  restart. Repeated runs reuse a build only after checking compiler/toolchain,
  source and artifact hashes.
- **Меню → Проверить и показать ASM** returns Python-generated ASM without an assembler.
  Action diagnostics resolve
  to a block via an editor-only source map; the error button selects that block.
- **Меню → Экспорт → Проект с блоками** transfers positions, IDs, collapsed state,
  draft blocks and viewport using `zxblocks/editor/v2`. Old editor/v1 files are
  still importable. The previous browser autosave migrates once into a separate
  project; compiler IR versions do not change. See [project storage and migration](../docs/PROJECTS.md).

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
- `src/project-session.js`: serialized revision-checked saves and browser recovery.
- `src/zxblocks/editor.py` in the repository: stdlib HTTP host, `/api/compile`.
- `src/zxblocks/runner.py`: fixed snapshot packaging and local emulator launch,
  shared by `/api/build`, `/api/run` and the independent `zxblocks run` command.
- `src/zxblocks/project_store.py`, `build_store.py`: filesystem projects,
  immutable build manifests, classification and verified reuse.
- `tests/`: real headless Blockly round trips, layout persistence, diagnostics,
  variable changes and a cross-language comparison of generated ASM.
- `scripts/build.mjs`: esbuild bundle, local media, license notices and example.

Blockly 13.4.0 and esbuild 0.28.2 are pinned with a lockfile. See
[third-party notices](THIRD_PARTY_NOTICES.md) for licenses. `dist/` and
`node_modules/` are generated and ignored by Git.

## Current limits and verification

There is no embedded Spectrum emulator, sprite editor, timer or user-procedure
support. The browser's run button launches the separate local EmuZWin app;
existing DeZog configurations remain available for the configured examples.
TAP downloads remain CODE-only; SNA provides direct startup. The server serves
a built repository checkout; standalone
Python wheels do not include editor assets. Changes to frontend sources require
`npm run build` and a page reload.

An incomplete/detached workspace can be saved and exported as an editor document,
but cannot compile or export valid IR. Filesystem saving is independent of
browser storage; keep a complete export or back up `projects/` to transfer work.
Diagnostics for project/variable declarations appear globally; diagnostics for
actions identify their blocks. Multiple tabs cannot overwrite a newer revision:
a conflict offers reopening or making a copy. Use one server per checkout.

On 2026-11-04 automated Python HTTP/diagnostic tests and real Blockly headless
tests passed, including ASM equality with the hand-written border example.
The browser bundle was built. **Interactive browser/visual QA remains pending:**
Computer Use stopped because it could not establish the current Chrome URL.
No interactive browser test is claimed.

The keyboard slice adds real-Blockly tests for v2 import/export, editor-state
restore, explicit format selection and all 40 key names. Browser/48K emulator
QA for the new keyboard example is also still pending. See
[the v2 specification](../docs/BLOCK_IR_V2.md) for migration and sampling rules.

The build/run slice adds HTTP tests for current-project snapshots, immutable
build links, missing tools, failed-build launch prevention, artifact access
and origin checks. Native sjasmplus tests validate generic v1/v2 BIN/SNA/SLD
output and native emulator path arguments. Interactive browser coverage is
still recorded separately; backend tests do not imply a browser click test.

The project-workspace iteration passed 61 Python tests and 21 Blockly/persistence
tests on 2026-11-04. A real managed HTTP build/run downloaded the user's 73-byte
program and valid 48K SNA, reused it before and after a server restart, and opened
EmuZWin. Detached-block restoration, concurrent saves, offline recovery,
revision conflicts, separated project histories, missing artifacts and failed
builds have automated coverage. Interactive menu/switching review remains open:
Computer Use's native pipe and browser access host were unavailable.
