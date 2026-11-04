# Projects and builds in the local workshop

## Interface

The top bar always names the active project and shows its save state.
**Открыть** (or the project name) opens the project list. **Сохранить** / Ctrl+S
writes the current document to disk immediately. Changes also autosave after
a short pause and before switching projects. **Запустить** / F5 saves and
builds the current program, then opens its SNA in EmuZWin.

The **Меню** groups less frequent actions: new project, duplicate, create from
either example, export a complete project, export compiler JSON, build without
launching, inspect ASM and fit all blocks. Examples create editable copies;
they do not replace another project or modify the example files.

**Открыть → Импортировать из файла** creates a new project from compiler IR,
an old `zxblocks/editor/v1` workspace, a new `zxblocks/editor/v2` document or
the workshop's stored workspace file. Imports are checked in a scratch Blockly
workspace before replacing the current one. The input file stays in place.
Use the old workspace file when you want its block positions as well as its IR.

The **Сборки** panel belongs to the active project. It shows numbered builds,
date/time, machine-code size, TAP/SNA downloads, logs and an explicit action to
launch that historical snapshot. JSON and Z80 ASM are secondary tabs. Save
status and whether the program matches a build are shown separately.

Program capabilities are inferred from connected blocks. A keyboard expression
automatically selects compiler IR v2 during export/save; no format selector or
confirmation is needed. Detached draft blocks do not enable a capability.
Previously v2 documents keep their version; removing the last keyboard use
excludes keyboard polling/runtime. Raw imported IR is validated against its
declared version before the editor touches the open project.

## Editor document v2 and migration

Compiler formats `zxblocks/v1` and `zxblocks/v2` and the Z80 ABI are unchanged.
`zxblocks/editor/v2` is a new **editor container**, with:

- `metadata`: name, current IR format, initial values keyed by variable IDs;
- `workspace`: Blockly serialization, including IDs, positions and detached blocks;
- `view`: scale, horizontal and vertical scroll;
- `project`: a matching valid compiler IR, or `null` for an unfinished draft.

Saving does not require a compilable program. Detached blocks, missing inputs,
disabled blocks and invalid initial values survive reopening; compilation still
rejects them. There is never a silent fallback to the previous valid program.
The browser exports this container through **Проект с блоками**; **JSON для
компилятора** exports only a currently valid IR.

The previous browser autosave `zxblocks.editor.v1` is imported once as a separate
project on first opening the new editor. A browser marker records the migrated
project ID; the original value is retained. Existing v1 workspace files remain
importable. This migration does not upgrade compiler IR v1 to v2.

## Filesystem

Paths below are relative to the repository; IDs are random, stable 32-digit
hex strings. Project names are labels, never filesystem paths or assembler text.
Renaming a project preserves its ID and its build history.

~~~text
projects/
  <project-id>/
    workspace.json             authoritative stored document and revision
    project.json               derived compiler IR, only while the draft is valid
build/
  projects/
    <project-id>/
      latest.json              newest successful build number
      000001/
        source/project.json    exact IR submitted for this build
        artifacts/project.*    BIN, TAP, SNA
        debug/                 ASM, SLD, snapshot wrapper, assembler output
        build.json             status, fingerprints, size and artifact hashes
        build.log
  examples/
    border_cycle/              VS Code build and DeZog inputs
    keyboard_border/
  checks/                      local verification reports
  cli/<source-folder>/         independent CLI output by default
  dezog/                       debugger temporary files
  legacy/                      preserved outputs from the previous layout
~~~

`workspace.json` uses `zxblocks/stored-project/v1`: project ID, revision,
creation/update timestamps and the editor `document`. It is replaced atomically.
`project.json` is a convenience export, not another source of editor state; it
is removed when a saved draft becomes invalid. A valid saved project can be run
from the independent CLI using `zxblocks run projects/<id>/project.json`.

User projects and build products are ignored by Git. Export a complete project
to transfer/back up the blocks and viewport; back up `projects/` to preserve all
workshop projects. Generated binaries remain outside version control.

## Persistence and conflicts

The browser remembers the last active project and a separate recovery document
per project. Files on disk survive browser-data cleanup and server restarts.
The server serializes operations; saves include the previously read revision.
Another tab's newer revision produces HTTP 409 instead of overwriting it.
Create a copy from the menu to retain conflicting edits, or reopen the current
project: its conflicting draft is saved as a separate recovered project first.
An older browser recovery found at startup also becomes a separate copy.

Failed saves retain a browser recovery and show an error beside the name.
Switching normally waits for a successful save. Recovery uses browser storage;
if that storage is unavailable, keep the page open until filesystem saving
succeeds or export the complete project. Use one editor server per checkout.

## Builds and API boundaries

The managed API is `/api/projects`, `/api/projects/<id>`, `.../save`,
`.../build`, `.../run` and `.../builds`. Downloads and explicit historical runs
are under `.../builds/<six-digit-number>/`. Clients supply documents or compiler
IR, never a local path, command or executable. POSTs keep the same-origin and
1 MiB limits. Only the six known artifacts and the build log are downloadable.

A successful build is immutable. Repeated build/run requests can reuse it only
when the exact IR, compiler source fingerprint, assembler executable hash and
48K target profile match, and all artifact hashes still match. Changes to layout
alone do not rebuild the program. Missing/edited output files force a new build.
Failure records keep their logs and do not update `latest.json` or launch an old
snapshot. History and downloads remain available after restarting the server.

The compiler/runner is shared with the independent CLI. Build/run default to
`build/cli/<source-folder>/` (previously `build/` and `build/run/` respectively);
explicit `-o` output paths still work as before. CLI outputs are replaced on
each run, whereas managed editor builds are immutable. The older raw-IR `/api/build` and `/api/run` endpoints
remain compatible, but the new UI uses only project-scoped builds. Existing
DeZog presets still debug the two examples, now in `build/examples/`. Opening a
managed project's arbitrary build in DeZog is not yet a UI action.

This iteration does not delete old builds automatically. Earlier anonymous
outputs can be kept under `build/legacy/`; they are not guessed into project
histories. Browser UI acceptance is recorded separately in the roadmap.
