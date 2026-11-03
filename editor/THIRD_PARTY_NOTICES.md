# Third-party notices

The editor pins Blockly **13.4.0**, maintained by the Raspberry Pi Foundation
and Blockly contributors, under **Apache-2.0**. Its copyright/license notices
are preserved in the bundle and `dist/BLOCKLY_LICENSE`; media files are copied
without modification. Source: https://github.com/RaspberryPiFoundation/blockly

The build tool esbuild **0.28.2** is licensed under **MIT**. It is used on the
host during bundling and is not shipped as executable code in the browser.
Source: https://github.com/evanw/esbuild

The exact transitive dependencies, versions and license identifiers are
recorded in `package-lock.json`. Their notices are retained in node_modules;
linked bundle notices are emitted as `app.js.LEGAL.txt` when applicable.
Blockly's Node-only jsdom dependencies are used by headless tests and are
excluded from the browser bundle. No CDN, fonts, or remote runtime assets are
required after the editor is built.

ZXBlocks' own editor code remains under the repository's MIT license.

The repository's optional Z80 tests use the external SkoolKit 10.1 tool
(GPL-3.0-or-later, https://skoolkit.ca/), installed separately via
`requirements-z80-tests.txt`. It is not bundled in the editor, linked into
Spectrum programs, or required by the compiler. No SkoolKit code or Spectrum
ROM assets are copied into this repository.
