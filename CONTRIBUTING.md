# How we collaborate with Codex

GitHub is the single source of truth. Discussions in chat can make architectural proposals; accepted decisions go to code, docs, issues or PRs. Do not maintain competing project versions in chats.

## Workflow

1. Agree on a small vertical slice and write acceptance checks.
2. Create a focused issue, then a feature branch (feat/blockly-editor, fix/tap-header, etc.).
3. Ask Codex to implement the issue, update tests and documentation.
4. Review the PR diff and check CI/emulator results.
5. Merge only after review; then select the next task.

Each PR should describe purpose, tests *actually run*, compatibility implications and limitations. Prefer squash merge. Coordinate concurrent edits of the IR and runtime ABI. Never commit secrets, system ROMs, local configuration or generated binaries.

## Verify locally

~~~sh
python -m pip install -e .
python -m unittest discover -s tests -v
python -m zxblocks compile examples/border_cycle/project.json -o build/border_cycle.asm
~~~

With sjasmplus on PATH:

~~~sh
python -m zxblocks build examples/border_cycle/project.json -o build
~~~

For editor changes (Node.js 22+), also run in `editor/`:

~~~sh
npm ci
npm test
npm run build
~~~

The cross-language editor test uses the repository `.venv` by default. Set
`ZXBLOCKS_PYTHON` to a Python executable with ZXBlocks installed when using a
different environment (CI sets it to `python`). Start `python -m zxblocks editor`
and check import/edit/export, workspace persistence, compile and block-linked
diagnostics in a browser. Report interactive browser QA separately from
headless Blockly tests. Keep the roadmap checkboxes aligned with actual evidence.

CODE-only TAP is not an autostart game: CLEAR 32767, then LOAD "" CODE, then RANDOMIZE USR 32768. If toolchain/emulator was unavailable, do not claim that verification succeeded.

When importing procedures from SpaceCan, document provenance, license, register/memory contract and T-states.
