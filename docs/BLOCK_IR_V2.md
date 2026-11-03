# Block IR — zxblocks/v2 (keyboard slice of M2)

`zxblocks/v2` preserves every v1 action, unsigned-byte rule and limit. The only
new expression in this slice is `{"key": "SPACE"}`. It yields u8 **1** if the
physical key is pressed and **0** otherwise. Use it wherever a byte expression
is accepted (`set.value` or `set_border.arg`). Comparisons still operate on a
declared variable and a byte literal. No wait, timer, procedure or object nodes
are introduced in this slice.

## Explicit migration and compatibility

Existing `zxblocks/v1` projects keep their original behavior and assembly.
They reject key expressions. Upgrade deliberately:

```sh
python -m zxblocks upgrade examples/border_cycle/project.json -o build/upgraded.json
```

The upgrade validates input, deep-copies it and changes only `format` to
`zxblocks/v2`. Input is not overwritten unless explicitly chosen as output.
Upgrading an already-v2 project is idempotent. A v1 project upgraded without
adding new expressions emits byte-identical ASM. There is no automatic
downgrade: remove key expressions before selecting v1 in the editor.

In Blockly, choose **v2 · клавиатура** in the project format selector, or open
the keyboard-border example. A key block in a v1 project produces a linked
diagnostic; the editor does not silently upgrade the project. The independent
`zxblocks/editor/v1` workspace envelope can contain either project version.

## Keyboard vocabulary

Names are case-sensitive physical key names; composed characters and `BREAK`
are not aliases. Shift combinations use their constituent physical keys.
The classic 48K matrix is defined by the [Sinclair manual, chapter 23](https://worldofspectrum.org/ZXBasicManual/zxmanchap23.html).
In each row below, keys are ordered from bit 0 through bit 4:

| Input port | Keys |
| --- | --- |
| FEFE | CAPS_SHIFT, Z, X, C, V |
| FDFE | A, S, D, F, G |
| FBFE | Q, W, E, R, T |
| F7FE | 1, 2, 3, 4, 5 |
| EFFE | 0, 9, 8, 7, 6 |
| DFFE | P, O, I, U, Y |
| BFFE | ENTER, L, K, J, H |
| 7FFE | SPACE, SYMBOL_SHIFT, M, N, B |

The compiler samples only referenced rows before the start event and once
after each HALT, before the frame event. Expressions reuse those samples;
holding a key stays 1, and release becomes 0 at the next poll. There is no
debounce, press-edge event, repeat timer or ROM keyboard-buffer dependency.
Rows are read sequentially; the whole physical matrix is not an atomic sample.
Only bits 0..4 are used; EAR and other input bits cannot affect the result.
See [the keyboard runtime contract](KEYBOARD_RUNTIME.md) for registers and RAM.

## Example and reference execution

`examples/keyboard_border/project.json` sets a blue border, then uses SPACE
to select yellow while held and blue while released. It is still native code
on the Spectrum. A host-side reference model can test logic independently:

```sh
python -m zxblocks simulate examples/keyboard_border/project.json --inputs examples/keyboard_border/inputs.json
python -m zxblocks simulate examples/border_cycle/project.json --frames 16
```

`--inputs` is an array of arrays of pressed key names, one array per frame.
The first frame's key sample is also used by the start event, which runs once.
`--frames` uses no pressed keys; the two flags are mutually exclusive. Traces
contain frame number, border and variable values. A trace is limited to 10000
frames. This is an IR logic model, not a Z80/48K emulator or timing profiler.
The model's initial border is 0 unless the start event sets it explicitly.
