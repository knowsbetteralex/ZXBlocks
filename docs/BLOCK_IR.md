# Block IR — zxblocks/v1

This remains the supported baseline. Keyboard expressions are a separate,
explicit [zxblocks/v2 extension](BLOCK_IR_V2.md); they are rejected in v1.

UTF-8 JSON is the boundary between future Blockly editor and compiler. Do not depend on Blockly's internal XML format.

~~~json
{
  "format": "zxblocks/v1",
  "name": "Border Cycle",
  "variables": [{"name": "counter", "initial": 0}],
  "events": {
    "start": [{"op": "set", "var": "counter", "value": 0}],
    "frame": [
      {"op": "change", "var": "counter", "by": 1},
      {"op": "if", "condition": {"var": "counter", "op": "ge", "value": 8},
       "then": [{"op": "set", "var": "counter", "value": 0}]},
      {"op": "call", "name": "set_border", "arg": {"var": "counter"}}
    ]
  }
}
~~~

## Rules

- format: exactly zxblocks/v1.
- variables: optional list; name is an ASCII identifier, unique ignoring case. initial is optional unsigned byte 0..255.
- events: optional object with start and frame arrays, executed sequentially.
- set: var = declared variable; value = expression.
- change: var = declared variable; by = integer -255..255; wraps modulo 256.
- if: condition containing var, comparison op (eq/ne/lt/ge), value (u8); optional then/else action arrays.
- call: name currently only set_border, arg = expression.
- expression: byte literal or object containing only var (declared variable).
- Comparison is unsigned. Nesting maximum 16, actions maximum 4096.
- Unsupported actions/variables/types cause compile errors.

## Codegen conventions

- ORG 32768, entry ZXB_START.
- Events ZXB_ON_START and ZXB_ON_FRAME.
- Builtins ZXB_RT_*, variables ZXB_VAR_* and deterministic unique branch labels.
- set_border input A is color, low 3 bits used; A and flags modified; writes port 254.

Current TAP is CODE-only without autostart: CLEAR 32767, then LOAD "" CODE, then RANDOMIZE USR 32768.

## Evolution

The editor preserves this format for basic programs. Blockly IDs, positions and
collapsed state are stored separately in `zxblocks/editor/v1` workspace files,
not in project IR. Missing optional arrays/defaults may be normalized on export;
reference spelling follows the declared variable. Unknown extension fields
are rejected by editor import to prevent silent data loss.

Python `CompileError.path` and the local editor HTTP diagnostic use paths such
as `events.frame[1].then[0]`. These are host-side diagnostic metadata, not an IR
schema change or runtime ABI change.

Versioned evolution can add word/signed types, non-blocking timers, procedures, object properties, sprite asset references, keyboard conditions, rich expressions and source maps. Create migrations and new tests; do not break existing projects silently.

Nested add/sub and expression comparisons are available in the separate
[v3 extension](BLOCK_IR_V3.md), not in v1 or v2. Further arithmetic still
precedes timers/waits; see [the implementation plan](ARITHMETIC_PLAN.md).
