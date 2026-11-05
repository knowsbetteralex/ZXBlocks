# Arithmetic and expressions — M2 work

Status: slice 1 implemented in [zxblocks/v3](BLOCK_IR_V3.md). The remaining
arithmetic/bitwise/logical operations below are planned. v1/v2 grammars stay unchanged.

On 2026-11-04 the user prioritized arithmetic before timers, delays and user
procedures. General expressions are needed for variable speeds, counters,
coordinates and conditions even before a renderer is available.

## Legacy baseline and implemented foundation

Legacy expressions contain a byte literal, a variable reference or a v2
keyboard sample. `change` adds a constant; legacy `if` compares a variable with a
constant using eq/ne/lt/ge in v1/v2. v3 now adds nested add/sub, six unsigned
expression comparisons, matching simulation and editor blocks. Bitwise nodes,
multiplication, division and remainder remain planned.

## Ordered implementation slices

1. **Expression foundation (implemented):** document a versioned IR extension and migration;
   add nested `+` and `-`, and comparisons between two expressions using
   `=`, `!=`, `<`, `<=`, `>` and `>=`. Expressions must work in assignments,
   supported builtin arguments and condition operands.
2. **Remaining arithmetic:** multiplication, unsigned integer division and
   remainder. Define division/remainder by zero before implementing them.
3. **Bits and conditions:** bytewise AND/OR/XOR/NOT and logical left/right
   shifts; distinguish them from logical condition AND/OR/NOT. Document shift
   counts, logical results and evaluation rules before coding those nodes.
4. **Complete acceptance:** finish the examples, compatibility checks and
   assembled-code checks for the above operations. Then start timers/waits.

Each slice includes its IR documentation, Python validation/code generation,
reference simulation, Blockly blocks, import/export, draft save/restore and
tests. Finish a working example in each slice instead of adding disconnected
compiler or editor features for all operators at once.

The next implementation task is slice 2: specify zero-divisor behavior and
add multiplication, division and remainder as further complete slices.

## Number model and decisions

Retain unsigned bytes, 0..255. Addition, subtraction and multiplication wrap
modulo 256 at each expression node, including intermediate results. There is
no implicit wider or signed arithmetic. Division returns an integer quotient;
remainder is a separate operation. Signed, word and fractional types are later
work and must not delay this stage.

Examples of the intended byte model: `255 + 1 = 0`, `0 - 1 = 255`,
`20 * 20 = 144`. Constant folding must follow the same per-node byte semantics
as the simulator and generated code; it cannot calculate a wider intermediate
and truncate only the final assignment.

Decide and specify before the relevant implementation:

- Results/diagnostics for a constant or runtime zero divisor, for both division
  and remainder; the compiler, constant folder and simulator must agree.
- Shift-count range and behavior outside it; right shift is logical for u8.
- Evaluation order, condition results and short-circuit rules. Logical
  conditions and bit masks must be unambiguous in the IR and block labels.
- The add/sub slice specifies depth 16, 4096 shared value nodes and balanced
  inline stack saves without scratch RAM. Further operators must retain or
  explicitly revise these documented limits/contracts before implementation.

## Compatibility and interface

- Keep current v1/v2 behavior and generated output unchanged. New nodes need a
  documented compiler IR version and migration; they do not extend old schemas
  implicitly or change the editor-container version just to add an operator.
- Preserve strict raw-IR import and compiler validation. The editor selects
  the required compiler version automatically from connected supported blocks.
- Show operations as nested value blocks and comparison/condition blocks;
  users do not select a file format or write assembler.
- Preserve incomplete expression trees as drafts, and tie errors to the
  offending input/block. A failed expression must never run an older build.
- Link helper routines only when used. Each routine needs the documented
  register/flags, stack, RAM and hardware contract required by AGENTS.md.

## Acceptance checks

- [x] v3 add/sub grammar, six comparisons, diagnostics, limits and migration documented.
- [x] Nested add/sub and expression comparisons work in the editor, CLI and simulator.
- [ ] Multiplication/division/remainder, masks, shifts and compound conditions work end to end.
- [x] Add/sub overflow, underflow, missing operands, malformed nodes and excessive nesting are tested.
- [ ] Zero-divisor and shift-boundary rules are specified and tested with their operators.
- [x] Add/sub and six comparisons match independent results in assembled Z80 execution; maximum-depth stack balance is checked.
- [ ] Remaining operators and any future constant folding match the byte model.
- [x] Original v1/v2 example ASM fingerprints remain unchanged.
- [x] Blocks round-trip through IR and saved drafts with automatic capability selection.
- [x] The arithmetic-border example assembles as a 48K snapshot and matches reference logic in assembled-code tests.
- [x] An isolated browser check creates/saves the arithmetic template, switches projects, restores it after reload, compiles, downloads and runs the same build.
- [ ] Interactive arithmetic/keyboard smoke test in a full 48K emulator.

Verified on 2026-11-05: 74 Python and 32 real-Blockly/persistence tests passed,
with no local skips. sjasmplus/SkoolKit execution checked 576 operand pairs,
all six comparisons, the keyboard example trace and the 34-byte maximum
additional comparison stack. The actual browser bundle passed an isolated
Chrome headless workflow, producing a 120-byte BIN and valid 48K SNA and
reusing that build through the Run button. EmuZWin launched in 48K mode and
reported responsive; visual keyboard acceptance remains pending because the
native UI helper did not expose its window.

The implemented `examples/arithmetic_border` combines variable increments,
expression comparisons and SPACE-controlled speed. A later example can derive
a border pattern from `(counter / divisor) AND 7`,
with keys changing operands. This demonstrates useful arithmetic before adding
delays. Sprite transparency masks remain part of graphics M3.
