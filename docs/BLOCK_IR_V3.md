# Block IR — zxblocks/v3: u8 addition, subtraction and expression comparisons

v3 preserves v1/v2 actions, legacy conditions and keyboard sampling. New value
expressions are `{"op":"add","left":expr,"right":expr}` and
`{"op":"sub","left":expr,"right":expr}`. Operands can be byte literals,
declared variables, cached key samples or nested add/sub expressions.

Each expression returns an unsigned byte: wrap modulo 256 at every node.
Evaluate left before right. `255 + 1` is 0; `0 - 1` is 255. There is no wider
intermediate, signed number, multiplication, division, bitwise or logical node
in this slice. All user text remains data; operators are strict enum values.

New conditions use two value expressions:

```json
{"op":"if", "condition": {
  "left":{"op":"add","left":{"var":"x"},"right":{"var":"speed"}},
  "op":"ge", "right":{"var":"limit"}
}, "then":[{"op":"set","var":"x","value":0}]}
```

Allowed comparisons are eq/ne/lt/le/gt/ge, all unsigned. They select a branch;
they are not byte-valued comparison expressions. Both operands are evaluated
once. `then`/`else` remain action arrays. The legacy `{var,op,value}` condition
retains its existing four operators eq/ne/lt/ge in every format, including v3.
Condition shapes cannot be mixed. `change.by` stays a constant -255..255; use
`set` with add/sub for variable increments.

## Limits and diagnostics

Keep 4096 actions and action nesting depth 16. Value trees have an independent
depth limit 16 (a root at depth 0) and a shared budget of 4096 expression nodes
per project. Leaves and operators count; the two new comparison operands are
separate depth-0 trees sharing that budget. Legacy fixed condition operands
are not value-expression trees. Missing operands, extra expression/condition
fields, unknown operators and unsupported formats fail before assembly.

New-expression diagnostics carry exact paths such as
`events.frame[0].value.right.left` and `events.frame[1].condition.right`.
The editor maps these paths to nested value blocks. Incomplete blocks remain
saveable editor drafts, and cannot compile or launch an older snapshot.

## Compatibility and migration

v1/v2 reject arithmetic and expression conditions. Their valid programs retain
byte-identical ASM. v3 also accepts unchanged legacy programs; upgrading one
without adding new nodes preserves its ASM and semantics. The CLI upgrade
command keeps v2 as its default and accepts an explicit `--to zxblocks/v3`.
Upgrades validate, deep-copy and never downgrade; a v3-to-v2 request fails.

The editor infers v3 from connected arithmetic/new-comparison blocks, including
inside event branches. It preserves older valid projects and previously
selected higher versions, and keeps keyboard support available in v3.
Editor container `zxblocks/editor/v2` and stored-project v1 are unchanged.

## Inline Z80 expression contract

Expression code uses only classic 48K instructions. Result: A; clobbers C and
flags for add/sub. B, DE, HL and index registers are unchanged. Left operands
are saved with PUSH AF and restored with POP AF; right results are copied to
C before ADD A,C / SUB C. No expression helper routine or scratch RAM is used.
The stack is balanced and intermediate values are private to the current call.

A maximum-depth value tree adds at most 32 stack bytes. Comparing two trees
can hold a saved left operand while evaluating the right: at most 34 additional
bytes, besides the event CALL return address and the existing interrupt stack.
IM 1 interrupts remain enabled and use the normal 48K ROM contract. Expressions
read cached keyboard bytes, never resample a port. T-states and ULA contention
are not measured by this contract; no timing guarantee is claimed.
