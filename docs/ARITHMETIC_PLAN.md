# Arithmetic and expressions — next M2 work

Status: planned, not implemented. This is the implementation plan, not an
extension of the currently accepted v1/v2 JSON grammar.

On 2026-11-04 the user prioritized arithmetic before timers, delays and user
procedures. General expressions are needed for variable speeds, counters,
coordinates and conditions even before a renderer is available.

## Current baseline

Expressions currently contain a byte literal, a variable reference or a v2
keyboard sample. `change` adds a constant; `if` compares a variable with a
constant using eq/ne/lt/ge. There are no general arithmetic or bitwise nodes.

## Ordered implementation slices

1. **Expression foundation:** document a versioned IR extension and migration;
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

The first implementation task is slice 1: `+`, `-` and comparisons of
expressions, all the way from blocks to a runnable Spectrum program.

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
- Limits on expression depth and total nodes, plus the register/stack/scratch
  RAM strategy for nested expressions. Existing action limits remain in force.

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

- [ ] Versioned grammar, operator semantics, diagnostics and migration documented.
- [ ] Nested arithmetic and expression comparisons work in the editor, CLI and simulator.
- [ ] Multiplication/division/remainder, masks, shifts and compound conditions work end to end.
- [ ] Overflow, underflow, zero divisors, shift boundaries, missing operands, malformed nodes and excessive nesting are tested.
- [ ] Byte-model results match constant folding and assembled Z80 execution; use boundary cases, reproducible samples and exhaustive u8 checks where practical.
- [ ] Original v1/v2 projects retain their behavior and deterministic output.
- [ ] Blocks round-trip through IR and saved drafts with automatic capability selection.
- [ ] A runnable arithmetic example is assembled and checked in a 48K emulator when available; unperformed checks are stated explicitly.

An initial example can combine variable increments and expression comparisons.
A later example can derive a border pattern from `(counter / divisor) AND 7`,
with keys changing operands. This demonstrates useful arithmetic before adding
delays. Sprite transparency masks remain part of graphics M3.
